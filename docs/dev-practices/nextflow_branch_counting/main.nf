// Branch-counting probe inside Nextflow: the same functions as step1/Probe.groovy, driven the same
// way, plus one workflow with channel closures (filter / map) that carry the same constructs.

def baseline(a) {
    if (a)
        return 1
    return 0
}

def and2(a, b) {
    if (a && b)
        return 1
    return 0
}

def or2(a, b) {
    if (a || b)
        return 1
    return 0
}

def and3(a, b, c) {
    if (a && b && c)
        return 1
    return 0
}

def elvis2(x, y) {
    def r = x ?: y
    return r
}

def elvis3(x, y, z) {
    def r = x ?: y ?: z
    return r
}

def ternary(a, x, y) {
    def r = a ? x : y
    return r
}

def safeNav(x) {
    def r = x?.size()
    return r
}

def closureAnd(a, b) {
    def c = { p, q ->
        if (p && q)
            return 1
        return 0
    }
    return c(a, b)
}

def sw(x) {
    switch (x) {
        case 1:
            return 'one'
        case 2:
            return 'two'
        case 3:
            return 'three'
    }
    return 'other'
}

// ---- extra constructs (second pass): negation, comparisons, membership, value-fed chains ----
def notA(a) {
    if (!a)
        return 1
    return 0
}

def eq(a, b) {
    if (a == b)
        return 1
    return 0
}

def inList(a) {
    if (a in [1, 2])
        return 1
    return 0
}

def instOf(a) {
    if (a instanceof String)
        return 1
    return 0
}

def gt(a) {
    if (a > 1)
        return 1
    return 0
}

def andValue(a, b) {
    def r = a && b
    return r
}

def and3Value(a, b, c) {
    def r = a && b && c
    return r
}

def or3(a, b, c) {
    if (a || b || c)
        return 1
    return 0
}

def notAnd(a, b) {
    if (!(a && b))
        return 1
    return 0
}

def ternaryAnd(a, b) {
    def r = a && b ? 1 : 0
    return r
}

workflow {
    // ---- driver: identical to step1 ----
    baseline(true); baseline(false)                       // full
    and2(true, true); and2(true, false); and2(false, true) // full
    or2(false, false)                                     // one way only
    and3(true, true, true)                                // one way only
    elvis2('x', 'y'); elvis2(null, 'y')                   // full
    elvis3('x', 'y', 'z')                                 // one way only
    ternary(true, 1, 2); ternary(false, 1, 2)             // full
    safeNav([1, 2])                                       // one way only
    closureAnd(true, true); closureAnd(true, false); closureAnd(false, true)  // full
    sw(1); sw(2)                                          // cases 1 and 2 only

    notA(true); notA(false)                                                    // full
    eq(1, 1); eq(1, 2)                                                         // full
    inList(1); inList(5)                                                       // full
    instOf('s'); instOf(1)                                                     // full
    gt(2); gt(0)                                                               // full
    andValue(true, true); andValue(true, false); andValue(false, true)         // full, value-fed
    and3Value(true, true, true); and3Value(true, true, false); and3Value(true, false, true); and3Value(false, true, true)  // full, value-fed
    or3(false, false, false); or3(false, false, true); or3(false, true, false); or3(true, false, false)                      // full
    notAnd(true, true); notAnd(true, false); notAnd(false, true)               // full
    ternaryAnd(true, true); ternaryAnd(true, false); ternaryAnd(false, true)   // full

    // ---- channel closures, like our .filter { } / .map { } operator bodies ----
    Channel.of([true, true], [true, false], [false, true])
        .filter { a, b ->
            if (a && b)
                return true
            return false
        }
        .map { a, b ->
            def r = a ?: b
            return r
        }
        .view { v -> "filtered: $v" }
    println 'probe done'
}
