using System;
using System.IO;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

class Program
{
    static void Main(string[] args)
    {
        if (args.Length == 0)
        {
            Console.WriteLine("Please provide a C# file to parse.");
            return;
        }

        string code = File.ReadAllText(args[0]);
        SyntaxTree tree = CSharpSyntaxTree.ParseText(code);
        var root = tree.GetRoot() as CompilationUnitSyntax;

        bool hasBasicHandling = false;
        bool hasAdvancedHandling = false;

        foreach (var node in root.DescendantNodes())
        {
            if (node is TryStatementSyntax)
                hasBasicHandling = true;

            if (node is InvocationExpressionSyntax invocation)
            {
                var expression = invocation.Expression.ToString();
                if (expression.Contains("timeout") || expression.Contains("retry") ||
                    expression.Contains("CircuitBreaker") || expression.Contains("backoff"))
                {
                    hasAdvancedHandling = true;
                }

                if (expression.Contains("StatusCode"))
                {
                    hasBasicHandling = true;
                }
            }
        }

        Console.WriteLine($"{hasBasicHandling},{hasAdvancedHandling}");
    }
}