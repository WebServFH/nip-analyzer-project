file://<WORKSPACE>/JavaParserAnalyzer.java
### java.util.NoSuchElementException: next on empty iterator

occurred in the presentation compiler.

presentation compiler configuration:


action parameters:
offset: 97
uri: file://<WORKSPACE>/JavaParserAnalyzer.java
text:
```scala
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
@@import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.TryStmt;
import com.github.javaparser.ast.stmt.ThrowStmt;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import org.json.JSONObject;

import java.io.File;
import java.io.FileNotFoundException;

public class JavaParserAnalyzer {
    private static boolean hasBasicHandling = false;
    private static boolean hasAdvancedHandling = false;

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Please provide a file path");
            System.exit(1);
        }

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
```



#### Error stacktrace:

```
scala.collection.Iterator$$anon$19.next(Iterator.scala:973)
	scala.collection.Iterator$$anon$19.next(Iterator.scala:971)
	scala.collection.mutable.MutationTracker$CheckedIterator.next(MutationTracker.scala:76)
	scala.collection.IterableOps.head(Iterable.scala:222)
	scala.collection.IterableOps.head$(Iterable.scala:222)
	scala.collection.AbstractIterable.head(Iterable.scala:935)
	dotty.tools.dotc.interactive.InteractiveDriver.run(InteractiveDriver.scala:164)
	dotty.tools.pc.MetalsDriver.run(MetalsDriver.scala:45)
	dotty.tools.pc.HoverProvider$.hover(HoverProvider.scala:40)
	dotty.tools.pc.ScalaPresentationCompiler.hover$$anonfun$1(ScalaPresentationCompiler.scala:376)
```
#### Short summary: 

java.util.NoSuchElementException: next on empty iterator