package main

import (
    "fmt"
    "go/ast"
    "go/parser"
    "go/token"
    "os"
    "strings"
)

func main() {
    if len(os.Args) < 2 {
        fmt.Println("false,false")
        return
    }

    filePath := os.Args[1]
    fset := token.NewFileSet()

    node, err := parser.ParseFile(fset, filePath, nil, parser.AllErrors)
    if err != nil {
        fmt.Println("false,false")
        fmt.Fprintln(os.Stderr, "Error parsing file:", err)
        return
    }

    hasBasicHandling := false
    hasAdvancedHandling := false

    ast.Inspect(node, func(n ast.Node) bool {
        switch x := n.(type) {
        case *ast.IfStmt:
            if cond, ok := x.Cond.(*ast.BinaryExpr); ok {
                if ident, ok := cond.X.(*ast.Ident); ok && ident.Name == "err" && cond.Op == token.NEQ {
                    if yIdent, ok := cond.Y.(*ast.Ident); ok && yIdent.Name == "nil" {
                        hasBasicHandling = true
                    }
                }
            }
        case *ast.CallExpr:
            if sel, ok := x.Fun.(*ast.SelectorExpr); ok {
                methodName := sel.Sel.Name
                if methodName == "StatusCode" || methodName == "Code" {
                    hasBasicHandling = true
                }
                if strings.Contains(methodName, "Timeout") || strings.Contains(methodName, "Retry") ||
                    strings.Contains(methodName, "CircuitBreaker") || strings.Contains(methodName, "Backoff") ||
                    strings.Contains(methodName, "Deadline") || strings.Contains(methodName, "Failover") {
                    hasAdvancedHandling = true
                }
            }
        }
        return true
    })

    fmt.Printf("%t,%t\n", hasBasicHandling, hasAdvancedHandling)
}
