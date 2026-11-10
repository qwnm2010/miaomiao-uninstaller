/*
 * libmiaomiao — small native filesystem accelerator for Miaomiao.
 *
 * It intentionally does one thing only: walk a path without following
 * symlinks and return the sum of regular-file sizes, under a time budget.
 * Python remains responsible for all destructive decisions and path safety.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

#define MM_MAX_DEPTH 64
#define MM_INVALID UINT64_MAX

static volatile sig_atomic_t mm_cancel_requested = 0;

__attribute__((visibility("default")))
void mm_cancel(void) {
    mm_cancel_requested = 1;
}

__attribute__((visibility("default")))
void mm_clear_cancel(void) {
    mm_cancel_requested = 0;
}

static uint64_t mono_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)(ts.tv_nsec / 1000000LL);
}

static uint64_t walk_path(const char *path, int depth, uint64_t deadline,
                          uint64_t *seen) {
    if (mm_cancel_requested) {
        return 0;
    }
    struct stat st;
    if (lstat(path, &st) != 0) {
        return 0;
    }
    if (S_ISLNK(st.st_mode)) {
        return 0;
    }
    if (S_ISREG(st.st_mode)) {
        return (uint64_t)st.st_size;
    }
    if (!S_ISDIR(st.st_mode) || depth >= MM_MAX_DEPTH) {
        return 0;
    }

    DIR *dir = opendir(path);
    if (!dir) {
        return 0;
    }

    uint64_t total = 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        if (mm_cancel_requested) {
            break;
        }
        if (((*seen)++ & 0x1ffU) == 0 && mono_ms() >= deadline) {
            break;
        }

        char child[PATH_MAX];
        int n = snprintf(child, sizeof(child), "%s/%s", path, entry->d_name);
        if (n <= 0 || (size_t)n >= sizeof(child)) {
            continue;
        }

        if (lstat(child, &st) != 0 || S_ISLNK(st.st_mode)) {
            continue;
        }
        if (S_ISREG(st.st_mode)) {
            total += (uint64_t)st.st_size;
        } else if (S_ISDIR(st.st_mode)) {
            if (!mm_cancel_requested) {
                total += walk_path(child, depth + 1, deadline, seen);
            }
        }
    }
    closedir(dir);
    return total;
}

__attribute__((visibility("default")))
uint64_t mm_dir_size(const char *path, int budget_ms) {
    if (!path || !*path) {
        return MM_INVALID;
    }
    struct stat st;
    if (lstat(path, &st) != 0) {
        return MM_INVALID;
    }
    if (S_ISLNK(st.st_mode)) {
        return 0;
    }
    if (S_ISREG(st.st_mode)) {
        return (uint64_t)st.st_size;
    }
    if (!S_ISDIR(st.st_mode)) {
        return 0;
    }
    if (mm_cancel_requested) {
        return 0;
    }
    if (budget_ms < 1) {
        budget_ms = 1;
    }
    uint64_t seen = 0;
    uint64_t deadline = mono_ms() + (uint64_t)budget_ms;
    return walk_path(path, 0, deadline, &seen);
}

__attribute__((visibility("default")))
uint64_t mm_paths_size(const char *const *paths, int count, int budget_ms) {
    if (!paths || count <= 0) {
        return 0;
    }
    uint64_t total = 0;
    uint64_t deadline = mono_ms() + (uint64_t)(budget_ms > 0 ? budget_ms : 1);
    for (int i = 0; i < count; i++) {
        if (!paths[i]) {
            continue;
        }
        uint64_t now = mono_ms();
        if (now >= deadline) {
            break;
        }
        uint64_t remaining = deadline - now;
        uint64_t result = mm_dir_size(paths[i], (int)remaining);
        if (result != MM_INVALID) {
            total += result;
        }
    }
    return total;
}
