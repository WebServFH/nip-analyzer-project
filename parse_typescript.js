const ts = require('typescript');
const fs = require('fs');

function parseTypeScript(filePath) {
    let code;
    try {
        code = fs.readFileSync(filePath, 'utf8');
    } catch (error) {
        console.error(JSON.stringify({
            error: `Error reading file: ${error.message}`
        }));
        process.exit(1);
    }

    try {
        const sourceFile = ts.createSourceFile(
            filePath,
            code,
            ts.ScriptTarget.Latest,
            true
        );

        let hasBasicHandling = false;
        let hasAdvancedHandling = false;

        function visit(node) {
            if (ts.isTryStatement(node)) {
                hasBasicHandling = true;
            } else if (ts.isCallExpression(node)) {
                const expression = node.expression;
                if (ts.isIdentifier(expression)) {
                    const name = expression.escapedText;
                    if (['timeout', 'retry', 'circuitBreaker', 'backoff'].includes(name)) {
                        hasAdvancedHandling = true;
                    }
                } else if (ts.isPropertyAccessExpression(expression) &&
                           ts.isIdentifier(expression.name) &&
                           expression.name.escapedText === 'status') {
                    hasBasicHandling = true;
                }
            }

            ts.forEachChild(node, visit);
        }

        visit(sourceFile);

        console.log(JSON.stringify({
            hasBasicHandling,
            hasAdvancedHandling
        }));
    } catch (error) {
        console.error(JSON.stringify({
            error: `Error parsing TypeScript: ${error.message}`
        }));
        process.exit(1);
    }
}

if (process.argv.length < 3) {
    console.error(JSON.stringify({
        error: 'Please provide a file path as an argument.'
    }));
    process.exit(1);
}

const filePath = process.argv[2];
parseTypeScript(filePath);