require 'yaml'
path = ARGV.fetch(0)
text = File.read(File.join(path, 'SKILL.md'))
match = /\A---\n(.*?)\n---/m.match(text) or abort('invalid front matter')
data = YAML.safe_load(match[1])
abort('not mapping') unless data.is_a?(Hash)
allowed = %w[name description license allowed-tools metadata]
abort('unexpected front matter keys') unless (data.keys - allowed).empty?
name = data['name']; desc = data['description']
abort('invalid name') unless name.is_a?(String) && name.match?(/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/) && name.size <= 64 && name == File.basename(path)
abort('invalid description') unless desc.is_a?(String) && !desc.strip.empty? && desc.size <= 1024 && !desc.match?(/[<>]/) && !desc.strip.start_with?('[TODO:')
body = text[match.end(0)..-1]
fence = nil
body.each_line do |line|
 if (m = line.match(/\A[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$/))
  if fence.nil? then fence = [m[1][0], m[1].size]
  elsif m[1][0] == fence[0] && m[1].size >= fence[1] && m[2].strip.empty? then fence = nil end
 elsif fence.nil? && line.match?(/\A[ ]{0,3}\[TODO:[^\n]*\][ \t]*\n?\z/)
  abort('unfinished TODO placeholder')
 end
end
puts "YAML and quick-validator-equivalent checks passed: #{name}"
