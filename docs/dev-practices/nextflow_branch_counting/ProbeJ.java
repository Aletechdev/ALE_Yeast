// Java reference for the same constructs (javac 17), run under the same JaCoCo agent.
import java.util.function.BiFunction;
public class ProbeJ {
    static int baseline(boolean a) {
        if (a)
            return 1;
        return 0;
    }
    static int and2(boolean a, boolean b) {
        if (a && b)
            return 1;
        return 0;
    }
    static int or2(boolean a, boolean b) {
        if (a || b)
            return 1;
        return 0;
    }
    static int and3(boolean a, boolean b, boolean c) {
        if (a && b && c)
            return 1;
        return 0;
    }
    static Object elvisLike(Object x, Object y) {
        Object r = x != null ? x : y;
        return r;
    }
    static Object ternary(boolean a, Object x, Object y) {
        Object r = a ? x : y;
        return r;
    }
    static int closureAnd(boolean a, boolean b) {
        BiFunction<Boolean, Boolean, Integer> c = (p, q) -> {
            if (p && q)
                return 1;
            return 0;
        };
        return c.apply(a, b);
    }
    static String sw(int x) {
        switch (x) {
            case 1:
                return "one";
            case 2:
                return "two";
            case 3:
                return "three";
        }
        return "other";
    }
    static int notA(boolean a) {
        if (!a)
            return 1;
        return 0;
    }
    static int eq(int a, int b) {
        if (a == b)
            return 1;
        return 0;
    }
    static boolean andValue(boolean a, boolean b) {
        boolean r = a && b;
        return r;
    }
    static boolean and3Value(boolean a, boolean b, boolean c) {
        boolean r = a && b && c;
        return r;
    }
    static int or3(boolean a, boolean b, boolean c) {
        if (a || b || c)
            return 1;
        return 0;
    }
    static int notAnd(boolean a, boolean b) {
        if (!(a && b))
            return 1;
        return 0;
    }
    static int ternaryAnd(boolean a, boolean b) {
        int r = a && b ? 1 : 0;
        return r;
    }
    public static void main(String[] args) {
        baseline(true); baseline(false);
        and2(true, true); and2(true, false); and2(false, true);
        or2(false, false);
        and3(true, true, true);
        elvisLike("x", "y"); elvisLike(null, "y");
        ternary(true, 1, 2); ternary(false, 1, 2);
        closureAnd(true, true); closureAnd(true, false); closureAnd(false, true);
        sw(1); sw(2);
        notA(true); notA(false);
        eq(1, 1); eq(1, 2);
        andValue(true, true); andValue(true, false); andValue(false, true);
        and3Value(true, true, true); and3Value(true, true, false); and3Value(true, false, true); and3Value(false, true, true);
        or3(false, false, false); or3(false, false, true); or3(false, true, false); or3(true, false, false);
        notAnd(true, true); notAnd(true, false); notAnd(false, true);
        ternaryAnd(true, true); ternaryAnd(true, false); ternaryAnd(false, true);
        System.out.println("java probe done");
    }
}
