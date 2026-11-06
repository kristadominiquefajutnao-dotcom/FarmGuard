class HashTable:
    def __init__(self, capacity=17):
        self.capacity = capacity
        self.buckets = [[] for _ in range(capacity)]
        self.size = 0

    def _index(self, key):
        return hash(str(key)) % self.capacity

    def insert(self, key, value):
        bucket = self.buckets[self._index(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self.size += 1

    def search(self, key):
        for stored_key, value in self.buckets[self._index(key)]:
            if stored_key == key:
                return value
        return None

    def delete(self, key):
        bucket = self.buckets[self._index(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                del bucket[i]
                self.size -= 1
                return True
        return False

    def __len__(self):
        return self.size
