class FarmNode:
    def __init__(self, name):
        self.name = name
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def traverse(self, level=0):
        lines = ["  " * level + self.name]
        for child in self.children:
            lines.extend(child.traverse(level + 1))
        return lines
