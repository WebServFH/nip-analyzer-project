const babel = require('@babel/core');
const fs = require('fs');

const filePath = process.argv[2];
const code = fs.readFileSync(filePath, 'utf8');

const ast = babel.parse(code, {
    plugins: ['@babel/plugin-syntax-jsx', '@babel/plugin-syntax-typescript', '@babel/plugin-syntax-class-properties', '@babel/plugin-syntax-object-rest-spread'],
    filename: filePath
});

let hasBasicHandling = false;
let hasAdvancedHandling = false;

babel.traverse(ast, {
    TryStatement() {
        hasBasicHandling = true;
    },
    CallExpression(path) {
        const callee = path.node.callee;
        if (callee.type === 'Identifier' && ['timeout', 'retry', 'circuitBreaker', 'backoff'].includes(callee.name)) {
            hasAdvancedHandling = true;
        } else if (callee.type === 'MemberExpression' && callee.property.name === 'status') {
            hasBasicHandling = true;
        }
    }
});

console.log(JSON.stringify({ hasBasicHandling, hasAdvancedHandling }));