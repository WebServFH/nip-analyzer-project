import java.io.File;
import java.io.FileNotFoundException;

import org.json.JSONObject;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.ThrowStmt;
import com.github.javaparser.ast.stmt.TryStmt;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ParserConfiguration;

public class JavaParserAnalyzer {
    private static boolean hasBasicHandling = false;
    private static boolean hasAdvancedHandling = false;

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Please provide a file path");
            System.exit(1);
        }

        ParserConfiguration config = new ParserConfiguration();
        config.setLanguageLevel(ParserConfiguration.LanguageLevel.RAW);
        StaticJavaParser.setConfiguration(config);

        String filePath = args[0];
        try {
            CompilationUnit cu = StaticJavaParser.parse(new File(filePath));
            cu.accept(new ErrorHandlingVisitor(), null);

            JSONObject result = new JSONObject();
            result.put("hasBasicHandling", hasBasicHandling);
            result.put("hasAdvancedHandling", hasAdvancedHandling);
            System.out.println(result.toString());
        } catch (FileNotFoundException e) {
            System.err.println("File not found: " + filePath);
            System.exit(1);
        }
    }

    private static class ErrorHandlingVisitor extends VoidVisitorAdapter<Void> {
        @Override
        public void visit(TryStmt n, Void arg) {
            hasBasicHandling = true;
            if (n.getFinallyBlock().isPresent()) {
                hasBasicHandling = true;
            }
            super.visit(n, arg);
        }

        @Override
        public void visit(CatchClause n, Void arg) {
            hasBasicHandling = true;
            super.visit(n, arg);
        }

        @Override
        public void visit(MethodDeclaration n, Void arg) {
            if (!n.getThrownExceptions().isEmpty()) {
                hasBasicHandling = true;
            }
            super.visit(n, arg);
        }

        @Override
        public void visit(MethodCallExpr n, Void arg) {
            String methodName = n.getNameAsString().toLowerCase();
            if (methodName.equals("timeout") || methodName.equals("retry") || 
                methodName.equals("circuitbreaker") || methodName.equals("backoff")) {
                hasAdvancedHandling = true;
            } else if (methodName.equals("statuscode")) {
                hasBasicHandling = true;
            }
            super.visit(n, arg);
        }

        @Override
        public void visit(ThrowStmt n, Void arg) {
            hasBasicHandling = true;
            super.visit(n, arg);
        }
    }
}