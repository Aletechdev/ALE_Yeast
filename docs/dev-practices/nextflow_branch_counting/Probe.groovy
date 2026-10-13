// Branch-counting probe: one construct per function, the decision on its own line.
// Written as a Groovy *script* (not a class) so groovyc produces `Probe extends groovy.lang.Script`
// with these as instance methods, the same shape Nextflow gives a .nf file's functions.

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

// ---- driver: some constructs covered every way, some only one way ----
baseline(true); baseline(false)                       // full
and2(true, true); and2(true, false); and2(false, true) // full: every operand both ways
or2(false, false)                                     // one way only: a false, b false, result false
and3(true, true, true)                                // one way only: all true
elvis2('x', 'y'); elvis2(null, 'y')                   // full
elvis3('x', 'y', 'z')                                 // one way only: first operand truthy
ternary(true, 1, 2); ternary(false, 1, 2)             // full
safeNav([1, 2])                                       // one way only: never null
closureAnd(true, true); closureAnd(true, false); closureAnd(false, true)  // full
sw(1); sw(2)                                          // cases 1 and 2 only; 3 and default never
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
println 'probe done'
