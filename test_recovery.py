from cbosa_client import (
    open_cbosa,
)


def main():

    print(
        "TEST NOWEGO RECOVERY"
    )

    response = open_cbosa()

    print(
        "Final status:",
        response.status_code
    )

    print(
        "Bytes:",
        len(response.content)
    )

    print(
        "TEST OK"
    )


if __name__ == "__main__":
    main()