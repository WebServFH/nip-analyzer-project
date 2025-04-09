import java.io.File

fun main(args: Array<String>) {
    try {
        if (args.isEmpty()) {
            println("false,false")
            return
        }

        val filePath = args[0]
        val file = File(filePath)
        
        if (!file.exists()) {
            println("false,false")
            return
        }

        val kotlinCode = file.readText()

        var hasBasicHandling = false
        var hasAdvancedHandling = false

        if ("try" in kotlinCode && "catch" in kotlinCode) {
            hasBasicHandling = true
        }

        if ("timeout" in kotlinCode || "retry" in kotlinCode || "CircuitBreaker" in kotlinCode || "backoff" in kotlinCode) {
            hasAdvancedHandling = true
        }

        if ("response.code" in kotlinCode || "response.statusCode" in kotlinCode) {
            hasBasicHandling = true
        }

        println("${hasBasicHandling.toString().lowercase()},${hasAdvancedHandling.toString().lowercase()}")
    } catch (e: Exception) {
        System.err.println("Error processing Kotlin file: ${e.message}")
        println("false,false")
    }
}