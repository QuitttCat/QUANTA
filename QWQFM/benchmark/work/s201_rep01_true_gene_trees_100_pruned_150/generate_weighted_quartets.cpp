#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::uint64_t choose4(std::uint64_t n) {
    return n * (n - 1) * (n - 2) * (n - 3) / 24;
}

class NewickParser {
  public:
    NewickParser(const std::string &text, int taxa)
        : text_(text), taxa_(taxa), next_internal_(taxa),
          adjacency_(2 * taxa + 8), seen_(taxa, false) {}

    std::vector<std::vector<int>> parse() {
        skip_space();
        parse_subtree();
        skip_space();
        if (position_ < text_.size() && text_[position_] == ';') {
            ++position_;
        }
        skip_space();
        if (position_ != text_.size()) {
            throw std::runtime_error("unexpected text after Newick tree");
        }
        for (int label = 0; label < taxa_; ++label) {
            if (!seen_[label]) {
                throw std::runtime_error("missing taxon " +
                                         std::to_string(label));
            }
        }
        adjacency_.resize(next_internal_);
        return adjacency_;
    }

  private:
    int parse_subtree() {
        skip_space();
        if (position_ >= text_.size()) {
            throw std::runtime_error("unexpected end of Newick tree");
        }
        if (text_[position_] == '(') {
            ++position_;
            const int node = allocate_internal();
            int child_count = 0;
            while (true) {
                const int child = parse_subtree();
                add_edge(node, child);
                ++child_count;
                skip_space();
                if (position_ >= text_.size()) {
                    throw std::runtime_error("unterminated internal node");
                }
                if (text_[position_] == ',') {
                    ++position_;
                    continue;
                }
                if (text_[position_] == ')') {
                    ++position_;
                    break;
                }
                throw std::runtime_error("expected ',' or ')' in Newick tree");
            }
            if (child_count != 2) {
                throw std::runtime_error("input tree is not binary");
            }
            skip_optional_label_and_length();
            return node;
        }

        const std::string token = read_token();
        if (token.empty() ||
            !std::all_of(token.begin(), token.end(),
                         [](unsigned char c) { return std::isdigit(c); })) {
            throw std::runtime_error("expected numeric leaf label");
        }
        const int label = std::stoi(token);
        if (label < 0 || label >= taxa_) {
            throw std::runtime_error("taxon outside requested range: " +
                                     std::to_string(label));
        }
        if (seen_[label]) {
            throw std::runtime_error("duplicate taxon " + std::to_string(label));
        }
        seen_[label] = true;
        skip_optional_length();
        return label;
    }

    int allocate_internal() {
        if (next_internal_ >= static_cast<int>(adjacency_.size())) {
            adjacency_.resize(adjacency_.size() * 2);
        }
        return next_internal_++;
    }

    void add_edge(int first, int second) {
        adjacency_[first].push_back(second);
        adjacency_[second].push_back(first);
    }

    std::string read_token() {
        skip_space();
        const std::size_t start = position_;
        while (position_ < text_.size()) {
            const char c = text_[position_];
            if (c == ':' || c == ',' || c == ')' || c == '(' || c == ';' ||
                std::isspace(static_cast<unsigned char>(c))) {
                break;
            }
            ++position_;
        }
        return text_.substr(start, position_ - start);
    }

    void skip_optional_label_and_length() {
        skip_space();
        if (position_ < text_.size() && text_[position_] != ':' &&
            text_[position_] != ',' && text_[position_] != ')' &&
            text_[position_] != ';') {
            read_token();
        }
        skip_optional_length();
    }

    void skip_optional_length() {
        skip_space();
        if (position_ >= text_.size() || text_[position_] != ':') {
            return;
        }
        ++position_;
        while (position_ < text_.size()) {
            const char c = text_[position_];
            if (c == ',' || c == ')' || c == ';') {
                break;
            }
            ++position_;
        }
    }

    void skip_space() {
        while (position_ < text_.size() &&
               std::isspace(static_cast<unsigned char>(text_[position_]))) {
            ++position_;
        }
    }

    const std::string &text_;
    int taxa_;
    int next_internal_;
    std::size_t position_ = 0;
    std::vector<std::vector<int>> adjacency_;
    std::vector<bool> seen_;
};

std::vector<std::vector<std::uint16_t>>
leaf_distances(const std::vector<std::vector<int>> &adjacency, int taxa) {
    std::vector<std::vector<std::uint16_t>> result(
        taxa, std::vector<std::uint16_t>(taxa));
    std::vector<int> distance(adjacency.size());
    std::queue<int> pending;

    for (int source = 0; source < taxa; ++source) {
        std::fill(distance.begin(), distance.end(), -1);
        distance[source] = 0;
        pending.push(source);
        while (!pending.empty()) {
            const int node = pending.front();
            pending.pop();
            for (const int neighbor : adjacency[node]) {
                if (distance[neighbor] == -1) {
                    distance[neighbor] = distance[node] + 1;
                    pending.push(neighbor);
                }
            }
        }
        for (int target = 0; target < taxa; ++target) {
            if (distance[target] < 0) {
                throw std::runtime_error("disconnected input tree");
            }
            result[source][target] =
                static_cast<std::uint16_t>(distance[target]);
        }
    }
    return result;
}

void add_tree_counts(const std::vector<std::vector<std::uint16_t>> &distance,
                     int taxa, std::vector<std::uint8_t> &first,
                     std::vector<std::uint8_t> &second) {
    std::uint64_t index = 0;
    for (int a = 0; a < taxa - 3; ++a) {
        for (int b = a + 1; b < taxa - 2; ++b) {
            for (int c = b + 1; c < taxa - 1; ++c) {
                for (int d = c + 1; d < taxa; ++d, ++index) {
                    const int sum0 = distance[a][b] + distance[c][d];
                    const int sum1 = distance[a][c] + distance[b][d];
                    const int sum2 = distance[a][d] + distance[b][c];
                    if (sum0 < sum1 && sum0 < sum2) {
                        ++first[index];
                    } else if (sum1 < sum0 && sum1 < sum2) {
                        ++second[index];
                    } else if (!(sum2 < sum0 && sum2 < sum1)) {
                        throw std::runtime_error(
                            "unresolved quartet encountered");
                    }
                }
            }
        }
    }
    if (index != first.size()) {
        throw std::runtime_error("quartet index-count mismatch");
    }
}

void write_quartet(std::ofstream &output, int a, int b, int c, int d,
                   int weight) {
    output << "((" << a << ',' << b << "),(" << c << ',' << d << ")); "
           << weight << '\n';
}

} // namespace

int main(int argc, char **argv) {
    try {
        if (argc != 5) {
            std::cerr << "Usage: " << argv[0]
                      << " INPUT_TREES OUTPUT_QUARTETS TAXA EXPECTED_TREES\n";
            return 2;
        }
        const std::string input_path = argv[1];
        const std::string output_path = argv[2];
        const int taxa = std::stoi(argv[3]);
        const int expected_trees = std::stoi(argv[4]);
        if (taxa < 4 || expected_trees < 1 || expected_trees > 255) {
            throw std::runtime_error("invalid taxa or expected-tree count");
        }

        const std::uint64_t quartet_subsets = choose4(taxa);
        std::vector<std::uint8_t> first(quartet_subsets, 0);
        std::vector<std::uint8_t> second(quartet_subsets, 0);

        std::ifstream input(input_path);
        if (!input) {
            throw std::runtime_error("cannot open input: " + input_path);
        }
        std::string line;
        int tree_count = 0;
        while (std::getline(input, line)) {
            if (line.find_first_not_of(" \t\r\n") == std::string::npos) {
                continue;
            }
            NewickParser parser(line, taxa);
            const auto adjacency = parser.parse();
            const auto distance = leaf_distances(adjacency, taxa);
            add_tree_counts(distance, taxa, first, second);
            ++tree_count;
            std::cerr << "counted tree " << tree_count << '/' << expected_trees
                      << '\n';
        }
        if (tree_count != expected_trees) {
            throw std::runtime_error("expected " +
                                     std::to_string(expected_trees) +
                                     " trees but read " +
                                     std::to_string(tree_count));
        }

        std::vector<char> output_buffer(8 * 1024 * 1024);
        std::ofstream output;
        output.rdbuf()->pubsetbuf(output_buffer.data(), output_buffer.size());
        output.open(output_path);
        if (!output) {
            throw std::runtime_error("cannot open output: " + output_path);
        }

        std::uint64_t index = 0;
        std::uint64_t output_lines = 0;
        std::uint64_t total_weight = 0;
        for (int a = 0; a < taxa - 3; ++a) {
            for (int b = a + 1; b < taxa - 2; ++b) {
                for (int c = b + 1; c < taxa - 1; ++c) {
                    for (int d = c + 1; d < taxa; ++d, ++index) {
                        const int weight0 = first[index];
                        const int weight1 = second[index];
                        const int weight2 =
                            tree_count - weight0 - weight1;
                        if (weight0 > 0) {
                            write_quartet(output, a, b, c, d, weight0);
                            ++output_lines;
                            total_weight += weight0;
                        }
                        if (weight1 > 0) {
                            write_quartet(output, a, c, b, d, weight1);
                            ++output_lines;
                            total_weight += weight1;
                        }
                        if (weight2 > 0) {
                            write_quartet(output, a, d, b, c, weight2);
                            ++output_lines;
                            total_weight += weight2;
                        }
                    }
                }
            }
        }
        output.close();
        if (!output) {
            throw std::runtime_error("failed while writing output");
        }

        const std::uint64_t expected_total_weight =
            quartet_subsets * static_cast<std::uint64_t>(tree_count);
        if (total_weight != expected_total_weight) {
            throw std::runtime_error("aggregate quartet-weight mismatch");
        }
        std::cout << "trees=" << tree_count << '\n'
                  << "taxa=" << taxa << '\n'
                  << "quartet_subsets=" << quartet_subsets << '\n'
                  << "output_lines=" << output_lines << '\n'
                  << "total_weight=" << total_weight << '\n';
    } catch (const std::exception &error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
