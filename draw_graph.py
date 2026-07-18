"""
Renders the compiled graph as a PNG for the README.

Run: python draw_graph.py
Produces: graph_diagram.png
"""

from graph import graph


def main():
    png_bytes = graph.get_graph().draw_mermaid_png()
    with open("graph_diagram.png", "wb") as f:
        f.write(png_bytes)
    print("Saved graph_diagram.png")

    # Also print the raw mermaid source, useful for pasting straight into
    # a GitHub README, which renders mermaid code blocks natively.
    print("\nMermaid source:\n")
    print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
