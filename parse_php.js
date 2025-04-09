const fs = require('fs');
const phpParser = require('php-parser');

const filePath = process.argv[2];

if (!filePath) {
    console.error('No file path provided');
    process.exit(1);
}

fs.readFile(filePath, 'utf8', (err, code) => {
    if (err) {
        console.error('Error reading file:', err);
        process.exit(1);
    }

    if (!code.trim()) {
        console.log(JSON.stringify({
            basicHandling: false,
            advancedHandling: false,
            error: "Empty or whitespace-only code",
            ast: null
        }));
        return;
    }

    try {
        const parser = new phpParser({
            parser: { 
                extractDoc: true, 
                suppressErrors: true 
            },
            ast: { 
                withPositions: true 
            }
        });

        const ast = parser.parseCode(code, filePath);
        const errors = parser.getLexer().errors.concat(parser.getErrors());

        let hasBasicHandling = false;
        let hasAdvancedHandling = false;

        const traverseNode = (node) => {
            if (!node) return;

            if (node.kind === 'try') {
                hasBasicHandling = true;
            }
            if (node.kind === 'call') {
                const functionName = node.what && node.what.name;
                if (functionName === 'curl_getinfo') {
                    hasBasicHandling = true;
                }
                if (['timeout', 'retry', 'CircuitBreaker', 'backoff'].includes(functionName)) {
                    hasAdvancedHandling = true;
                }
            }
            for (const key in node) {
                if (node[key] && typeof node[key] === 'object') {
                    traverseNode(node[key]);
                }
            }
        };

        traverseNode(ast);

        console.log(JSON.stringify({
            basicHandling: hasBasicHandling,
            advancedHandling: hasAdvancedHandling,
            ast: ast,
            errors: errors.map(error => ({
                message: error.message,
                line: error.line,
                column: error.column
            }))
        }));
    } catch (parseError) {
        console.error('Error parsing PHP code:', parseError.message);
        console.log(JSON.stringify({
            basicHandling: false,
            advancedHandling: false,
            error: parseError.message,
            ast: null
        }));
    }
});
