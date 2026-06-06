import sys


def fizzbuzz(n):
    """Return list of FizzBuzz lines for 1..n."""
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:          # divisible by both 3 and 5
            out.append("FizzBuzz")
        elif i % 3 == 0:         # divisible by 3 only
            out.append("Fizz")
        elif i % 5 == 0:         # divisible by 5 only
            out.append("Buzz")
        else:                    # otherwise the number itself
            out.append(str(i))
    return out


def main():
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    # single write -> fast even for n ~ 2e5
    sys.stdout.write("\n".join(fizzbuzz(n)) + "\n")


if __name__ == "__main__":
    main()
