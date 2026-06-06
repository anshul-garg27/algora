import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/* ---------- Domain ---------- */

final class Train {
    final String id;
    final int arrival;   // requested arrival time
    final int duration;  // how long it needs a platform (end - start)
    Train(String id, int arrival, int departure) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("train id required");
        if (departure <= arrival) throw new IllegalArgumentException("departure must be > arrival");
        this.id = id; this.arrival = arrival; this.duration = departure - arrival;
    }
}

/* A confirmed reservation of a platform for a time window [start, end). */
final class Booking {
    final String trainId;
    final int platform;   // 1-based
    final int start, end;
    Booking(String trainId, int platform, int start, int end) {
        this.trainId = trainId; this.platform = platform; this.start = start; this.end = end;
    }
    boolean covers(int t) { return t >= start && t < end; }
    public String toString() {
        return "Train " + trainId + " @P" + platform + " [" + start + "," + end + ")";
    }
}

/* Factory: single place that constructs validated Train objects. */
final class TrainFactory {
    static Train create(String id, int arrival, int departure) {
        return new Train(id, arrival, departure);
    }
}

/* ---------- Strategy: how to pick a platform / slot ---------- */

interface PlatformSelectionStrategy {
    // returns chosen platform (1-based) and the start time it can begin
    int[] select(List<Platform> platforms, int arrival, int duration);
}

/* Pick the platform that lets the train start the earliest; tie -> lowest number. */
final class EarliestAvailableStrategy implements PlatformSelectionStrategy {
    public int[] select(List<Platform> platforms, int arrival, int duration) {
        int bestPlatform = -1, bestStart = Integer.MAX_VALUE;
        for (Platform p : platforms) {
            int s = p.earliestSlot(arrival, duration);
            if (s < bestStart) { bestStart = s; bestPlatform = p.number; }
        }
        return new int[]{bestPlatform, bestStart};
    }
}

/* ---------- Observer: react to assignment events ---------- */

interface AssignmentObserver {
    void onAssigned(Booking b, boolean waited);
}

final class LoggingObserver implements AssignmentObserver {
    final List<String> log = new ArrayList<>();
    public void onAssigned(Booking b, boolean waited) {
        log.add((waited ? "WAITED " : "IMMEDIATE ") + b);
    }
}

/* ---------- Platform ---------- */

final class Platform {
    final int number;
    private final List<Booking> bookings = new ArrayList<>(); // sorted by start

    Platform(int number) { this.number = number; }

    /* earliest start >= arrival where a window of `duration` fits with no overlap */
    int earliestSlot(int arrival, int duration) {
        int candidate = arrival;
        for (Booking b : bookings) {            // bookings kept sorted by start
            if (candidate + duration <= b.start) return candidate; // fits before this booking
            if (b.end > candidate) candidate = b.end;              // pushed past this booking
        }
        return candidate;
    }

    void add(Booking b) {
        int i = 0;
        while (i < bookings.size() && bookings.get(i).start < b.start) i++;
        bookings.add(i, b);
    }

    Booking at(int t) {
        for (Booking b : bookings) if (b.covers(t)) return b;
        return null;
    }
}

/* ---------- Orchestrator ---------- */

final class Station {
    private final List<Platform> platforms = new ArrayList<>();
    private final Map<String, List<Booking>> byTrain = new HashMap<>();
    private final PlatformSelectionStrategy strategy;
    private final List<AssignmentObserver> observers = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    Station(int numPlatforms, PlatformSelectionStrategy strategy) {
        if (numPlatforms <= 0) throw new IllegalArgumentException("need >=1 platform");
        for (int i = 1; i <= numPlatforms; i++) platforms.add(new Platform(i));
        this.strategy = strategy;
    }

    void addObserver(AssignmentObserver o) { observers.add(o); }

    /* Assign a train. Always returns a Booking (waits/queues by shifting start). */
    Booking assign(Train train) {
        lock.lock();
        try {
            if (byTrain.containsKey(train.id))
                throw new IllegalStateException("duplicate train id: " + train.id);

            int[] choice = strategy.select(platforms, train.arrival, train.duration);
            int platformNo = choice[0], start = choice[1];
            Platform p = platforms.get(platformNo - 1);

            Booking b = new Booking(train.id, platformNo, start, start + train.duration);
            p.add(b);
            byTrain.computeIfAbsent(train.id, k -> new ArrayList<>()).add(b);

            boolean waited = start > train.arrival;
            for (AssignmentObserver o : observers) o.onAssigned(b, waited);
            return b;
        } finally { lock.unlock(); }
    }

    /* Query 1: which train occupies a platform at time t? (null if none) */
    String trainAtPlatform(int platformNo, int t) {
        lock.lock();
        try {
            if (platformNo < 1 || platformNo > platforms.size())
                throw new IllegalArgumentException("bad platform: " + platformNo);
            Booking b = platforms.get(platformNo - 1).at(t);
            return b == null ? null : b.trainId;
        } finally { lock.unlock(); }
    }

    /* Query 2: which platform does a train occupy at time t? (-1 if not there) */
    int platformOfTrain(String trainId, int t) {
        lock.lock();
        try {
            for (Booking b : byTrain.getOrDefault(trainId, List.of()))
                if (b.covers(t)) return b.platform;
            return -1;
        } finally { lock.unlock(); }
    }
}

/* ---------- Driver / assertions ---------- */

public class TrainPlatformDemo {
    static void check(boolean c, String msg) {
        if (!c) throw new AssertionError("FAIL: " + msg);
        System.out.println("ok - " + msg);
    }

    public static void main(String[] args) {
        LoggingObserver log = new LoggingObserver();
        Station st = new Station(2, new EarliestAvailableStrategy());
        st.addObserver(log);

        Booking a = st.assign(TrainFactory.create("A", 0, 30));   // P1 [0,30)
        Booking b = st.assign(TrainFactory.create("B", 5, 25));   // P2 [5,25)
        check(a.platform == 1 && b.platform == 2, "first two trains get distinct platforms");

        // both platforms busy at t=10 -> C must WAIT for earliest free (P2 frees at 25)
        Booking c = st.assign(TrainFactory.create("C", 10, 20));  // dur 10
        check(c.start == 25 && c.platform == 2, "C waits until a platform frees (P2 @25)");

        // queries
        check("A".equals(st.trainAtPlatform(1, 10)), "P1 holds A at t=10");
        check(st.trainAtPlatform(1, 30) == null, "P1 empty at t=30 (end exclusive)");
        check(st.platformOfTrain("B", 5) == 2, "B on P2 at t=5");
        check(st.platformOfTrain("C", 26) == 2, "C on P2 at t=26 after waiting");
        check(st.platformOfTrain("C", 10) == -1, "C not present yet at t=10");

        // boundary / invalid
        boolean threw = false;
        try { st.assign(TrainFactory.create("A", 100, 110)); } catch (IllegalStateException e) { threw = true; }
        check(threw, "duplicate train id rejected");

        threw = false;
        try { TrainFactory.create("X", 50, 50); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "zero-length stay rejected");

        threw = false;
        try { st.trainAtPlatform(99, 5); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "out-of-range platform rejected");

        System.out.println("\n--- assignment log ---");
        log.log.forEach(System.out::println);
        System.out.println("\nALL PASSED");
    }
}
