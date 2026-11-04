"""Port of stackchan/utils/object_pool.h."""


class Poolable(object):
    def __init__(self):
        self._destroy_requested = False

    def request_destroy(self):
        self._destroy_requested = True

    def is_destroy_requested(self):
        return self._destroy_requested


class ObjectPool(object):
    """Id-addressed pool with deferred destruction (cleanup())."""

    def __init__(self):
        self._items = {}
        self._next_id = 0

    def create(self, item):
        item_id = self._next_id
        self._next_id += 1
        self._items[item_id] = item
        return item_id

    def get(self, item_id):
        return self._items.get(item_id)

    def destroy(self, item_id):
        item = self._items.pop(item_id, None)
        if item is None:
            return False
        on_destroy = getattr(item, 'on_destroy', None)
        if on_destroy:
            on_destroy()
        return True

    def for_each(self, callback):
        for item_id, item in list(self._items.items()):
            callback(item, item_id)

    def cleanup(self):
        for item_id, item in list(self._items.items()):
            if item.is_destroy_requested():
                self.destroy(item_id)

    def clear(self):
        for item_id in list(self._items.keys()):
            self.destroy(item_id)