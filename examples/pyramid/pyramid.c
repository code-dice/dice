#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <errno.h>

int main(int argc, char **argv) {
    int a[1000];
    int i;
    long idx;
    char *endptr, *str;

    str = argv[1];

    idx = strtol(str, &endptr, 10);

    if (errno == ERANGE && idx == LONG_MAX) {
        fprintf(stderr, "Error: Number overflow");
        return 1;
    }

    if (str == endptr) {
        fprintf(stderr, "Error: Invalid number");
        return 1;
    }

    if (idx > 1000) {
        fprintf(stderr, "Error: Max input is 1000");
        return 1;
    }

    if (idx < 0) {
        fprintf(stderr, "Error: Min input is 0");
        return 1;
    }


    for (i = 0; i < 1000; i++) {
        if (i == 0)
            a[i] = i * i;
        else
            a[i] = i * i + a[i - 1];
    }

    printf("%d\n", a[idx]);
    return 0;
}
