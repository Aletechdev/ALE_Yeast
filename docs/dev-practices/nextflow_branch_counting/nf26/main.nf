// Branch-counting probe in strict Nextflow syntax (26.x default parser). Independent of the pipeline.

def and2(a, b) {
    if (a && b)
        return 1
    return 0
}

def elvis3(x, y, z) {
    def r = x ?: y ?: z
    return r
}

def notA(a) {
    if (!a)
        return 1
    return 0
}

process ECHO {
    input:
    val x

    output:
    stdout

    script:
    """
    echo "got ${x}"
    """
}

workflow {
    and2(true, true); and2(true, false); and2(false, true)
    elvis3('x', 'y', 'z')
    notA(true); notA(false)

    ch = channel.of(1, 2, 3)
        .branch { v ->
            small: v < 2
            other: true
        }
    ch.other.map { v -> v * 10 }.view { v -> "mapped: ${v}" }
    ECHO(ch.small)
    ECHO.out.view()
}
