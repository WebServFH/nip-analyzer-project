begin
  gem 'parser', '>= 3.0.0'
  require 'parser/current'
rescue Gem::LoadError => e
  puts "Error: #{e.message}"
  puts "false,false"
  exit 1
end

def analyze_ruby_code(code)
  begin
    ast = Parser::CurrentRuby.parse(code)
  rescue Parser::SyntaxError => e
    puts "false,false"  # Default to no error handling detected if parsing fails
    return
  end

  has_basic_handling = false
  has_advanced_handling = false

  # Traverse the AST to find patterns
  process_node = lambda do |node|
    next unless node.is_a?(Parser::AST::Node)

    case node.type
    when :rescue
      has_basic_handling = true
    when :send
      method_name = node.children[1]
      if [:retry, :timeout, :circuitbreaker, :backoff].include?(method_name)
        has_advanced_handling = true
      end
      if method_name == :code && node.children[0].children[1] == :response
        has_basic_handling = true
      end
    end

    node.children.each { |child| process_node.call(child) }
  end

  process_node.call(ast)

  puts "#{has_basic_handling},#{has_advanced_handling}"
end

if ARGV.empty?
  puts "No Ruby code file provided."
  exit 1
end

file_path = ARGV[0]
begin
  ruby_code = File.read(file_path)
  analyze_ruby_code(ruby_code)
rescue => e
  puts "Error reading or processing file: #{e.message}"
  puts "false,false"  # Default to no error handling detected if file reading fails
end