class MaxHeap:
    def __init__(self):
        self.items = []

    def __len__(self):
        return len(self.items)

    def is_empty(self):
        return len(self.items) == 0

    def insert(self, item):
        self.items.append(item)
        self._sift_up(len(self.items) - 1)

    def peek(self):
        return self.items[0] if self.items else None

    def extract_max(self):
        if not self.items:
            return None
        if len(self.items) == 1:
            return self.items.pop()
        maximum = self.items[0]
        self.items[0] = self.items.pop()
        self._sift_down(0)
        return maximum

    def _sift_up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            if self.items[parent][0] >= self.items[index][0]:
                break
            self.items[parent], self.items[index] = self.items[index], self.items[parent]
            index = parent

    def _sift_down(self, index):
        size = len(self.items)
        while True:
            largest = index
            left, right = 2 * index + 1, 2 * index + 2
            if left < size and self.items[left][0] > self.items[largest][0]:
                largest = left
            if right < size and self.items[right][0] > self.items[largest][0]:
                largest = right
            if largest == index:
                break
            self.items[index], self.items[largest] = self.items[largest], self.items[index]
            index = largest
