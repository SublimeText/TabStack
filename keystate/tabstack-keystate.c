/*
 * tabstack-keystate - reports whether a Ctrl key is held, for the TabStack
 * Sublime Text package.
 *
 * A native Wayland client cannot query the global keyboard state, so TabStack
 * cannot tell when Ctrl is released after Ctrl+Tab. This helper reads the key
 * state from the kernel's evdev devices (/dev/input/event*) instead.
 *
 * Those devices are readable only by root and the `input` group. Installed with
 * `cap_dac_read_search=ep`, the helper can open them read-only without either.
 * It sets no_new_privs first and drops all capabilities right after opening
 * the devices, before it reads any input or reports anything that depends on
 * them.
 *
 * Protocol, version 1: ASCII lines on stdout, each flushed.
 *   "tabstack-keystate 1" first, then either "error <code> <message>" and
 *   exit status 1, or the state ("1" while a Ctrl key is held, else "0")
 *   followed by one line per change. Exits 0 when stdin reaches EOF.
 *
 * Build: cc -std=c11 -O2 -Wall -Wextra -o tabstack-keystate tabstack-keystate.c
 */
#define _DEFAULT_SOURCE

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/capability.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MAX_DEVICES 64
#define BITS_PER_LONG (8 * sizeof(unsigned long))
#define KEY_LONGS ((KEY_CNT + BITS_PER_LONG - 1) / BITS_PER_LONG)

static int devices[MAX_DEVICES];
static int device_count;

static void emit(const char *line) {
    if (puts(line) == EOF || fflush(stdout) == EOF) {
        exit(errno == EPIPE ? 0 : 1);
    }
}

static void fail(const char *code, const char *message) {
    char line[256];
    snprintf(line, sizeof line, "error %s %s", code, message);
    emit(line);
    exit(1);
}

static bool has_ctrl(const unsigned long *keys) {
    const unsigned int codes[] = {KEY_LEFTCTRL, KEY_RIGHTCTRL};
    for (size_t i = 0; i < sizeof codes / sizeof codes[0]; i++) {
        if ((keys[codes[i] / BITS_PER_LONG] >> (codes[i] % BITS_PER_LONG)) & 1UL) {
            return true;
        }
    }
    return false;
}

/*
 * Reads the key capabilities that sysfs exposes for `name`, so that devices
 * without a Ctrl key need not be opened: closing an evdev device waits for an
 * RCU grace period, which adds up to hundreds of milliseconds before the
 * initial state could be reported. The file holds hex longs, most significant
 * first, with leading zero longs omitted. Returns false if it cannot be read.
 */
static bool read_sysfs_keys(const char *name, unsigned long *keys) {
    char path[128];
    int length = snprintf(path, sizeof path, "/sys/class/input/%s/device/capabilities/key", name);
    if (length < 0 || (size_t)length >= sizeof path) {
        return false;
    }
    FILE *file = fopen(path, "re");
    if (file == NULL) {
        return false;
    }
    char line[KEY_LONGS * 17 + 2];
    bool ok = fgets(line, sizeof line, file) != NULL;
    fclose(file);
    if (!ok) {
        return false;
    }

    unsigned long words[KEY_LONGS];
    size_t count = 0;
    for (char *token = strtok(line, " \n"); token != NULL; token = strtok(NULL, " \n")) {
        if (count == KEY_LONGS) {
            return false;
        }
        char *end;
        errno = 0;
        words[count++] = strtoul(token, &end, 16);
        if (errno != 0 || *end != '\0') {
            return false;
        }
    }
    for (size_t i = 0; i < count; i++) {
        keys[i] = words[count - 1 - i];
    }
    return true;
}

/* Opens every device with a Ctrl key. Returns whether any open was denied. */
static bool open_keyboards(void) {
    DIR *dir = opendir("/dev/input");
    if (dir == NULL) {
        return errno == EACCES || errno == EPERM;
    }
    bool denied = false;
    struct dirent *entry;
    while (device_count < MAX_DEVICES && (entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "event", 5) != 0) {
            continue;
        }
        unsigned long sysfs_keys[KEY_LONGS] = {0};
        if (read_sysfs_keys(entry->d_name, sysfs_keys) && !has_ctrl(sysfs_keys)) {
            continue;
        }
        int fd = openat(dirfd(dir), entry->d_name, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) {
            denied = denied || errno == EACCES || errno == EPERM;
            continue;
        }
        unsigned long keys[KEY_LONGS] = {0};
        if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof keys), keys) < 0 || !has_ctrl(keys)) {
            close(fd);
            continue;
        }
        devices[device_count++] = fd;
    }
    closedir(dir);
    return denied;
}

/* Raw capset(2) instead of libcap, so that building needs no extra library. */
static int drop_capabilities(void) {
    struct __user_cap_header_struct header = {.version = _LINUX_CAPABILITY_VERSION_3, .pid = 0};
    struct __user_cap_data_struct data[_LINUX_CAPABILITY_U32S_3];
    memset(data, 0, sizeof data);
    return (int)syscall(SYS_capset, &header, data);
}

static int ctrl_state(void) {
    for (int i = 0; i < device_count; i++) {
        unsigned long keys[KEY_LONGS] = {0};
        if (ioctl(devices[i], EVIOCGKEY(sizeof keys), keys) >= 0 && has_ctrl(keys)) {
            return 1;
        }
    }
    return 0;
}

/* Discards pending events; only EVIOCGKEY matters. Returns false once the device is gone. */
static bool drain(int fd) {
    struct input_event events[64];
    for (;;) {
        ssize_t n = read(fd, events, sizeof events);
        if (n > 0 || (n < 0 && errno == EINTR)) {
            continue;
        }
        return n < 0 && errno == EAGAIN;
    }
}

/* Returns false on stdin EOF, hangup or error. */
static bool stdin_open(short revents) {
    if (!(revents & (POLLIN | POLLHUP | POLLERR | POLLNVAL))) {
        return true;
    }
    char buffer[256];
    ssize_t n = read(STDIN_FILENO, buffer, sizeof buffer);
    return n > 0 || (n < 0 && (errno == EINTR || errno == EAGAIN));
}

int main(void) {
    signal(SIGPIPE, SIG_IGN);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        perror("tabstack-keystate: prctl");
        return 1;
    }
    emit("tabstack-keystate 1");

    bool denied = open_keyboards();
    if (drop_capabilities() != 0) {
        fail("capset", strerror(errno));
    }
    if (device_count == 0) {
        if (denied) {
            fail("no-access", "cannot open /dev/input/event* (is cap_dac_read_search set?)");
        }
        fail("no-keyboards", "no input device has a Ctrl key");
    }

    int state = ctrl_state();
    emit(state ? "1" : "0");

    for (;;) {
        struct pollfd fds[MAX_DEVICES + 1];
        fds[0] = (struct pollfd){.fd = STDIN_FILENO, .events = POLLIN};
        for (int i = 0; i < device_count; i++) {
            fds[i + 1] = (struct pollfd){.fd = devices[i], .events = POLLIN};
        }
        if (poll(fds, (nfds_t)device_count + 1, -1) < 0) {
            if (errno == EINTR) {
                continue;
            }
            return 1;
        }
        if (!stdin_open(fds[0].revents)) {
            return 0;
        }
        /* Backwards, so that moving the last device into a removed slot is safe. */
        for (int i = device_count - 1; i >= 0; i--) {
            short revents = fds[i + 1].revents;
            bool gone = revents & (POLLERR | POLLHUP | POLLNVAL);
            if (!gone && (revents & POLLIN)) {
                gone = !drain(devices[i]);
            }
            if (gone) {
                close(devices[i]);
                devices[i] = devices[--device_count];
            }
        }
        int next = ctrl_state();
        if (next != state) {
            state = next;
            emit(state ? "1" : "0");
        }
    }
}
