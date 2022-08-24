from this import d
from .settings_manager import SettingsManager

import logging

log = logging.getLogger(__name__)


class BookmarkManager:
    def __init__(self):
        self.settings_manager = SettingsManager()

    def save_bookmark(self, bookmark, i=-1):
        if i == -1:
            stored_bookmarks = self.get_bookmarks()
            nr_of_bookmarks = len(stored_bookmarks)
            new_bm_i = nr_of_bookmarks + 1
        else:
            new_bm_i = i
        self.settings_manager.store_setting(f"favourite_{new_bm_i}", bookmark)

    def get_bookmarks(self):
        bookmarks = []
        i = 1
        while True:
            bookmark = self.settings_manager.get_setting(f"favourite_{i}")
            if bookmark is None:
                break
            bookmarks.append(bookmark)
            i += 1
        return bookmarks

    def get_bookmark_index(self, bookmark):
        """
        Return 0-based index of bookmark in stored bookmarks list.
        """
        stored_bookmarks = self.get_bookmarks()
        # find index of fav layer to delete
        logging.debug(f"nr of bookmarks: {len(stored_bookmarks)}")
        bookmark_index = -1
        for i in range(0, len(stored_bookmarks)):
            stored_bookmark = stored_bookmarks[i]
            if self.bookmarks_equal(stored_bookmark, bookmark):
                bookmark_index = i
                break
        return bookmark_index

    def bookmarks_equal(self, lyr, bookmark):
        """
        check for layer equality based on equal
        - service_md_id
        - name (layername)
        - style (in case of WMS layer)
        """
        # fix #77: names of keys have been changed, so IF there is an old set, try to fix
        if "service_md_id" not in bookmark:
            if "md_id" in bookmark:
                # local migration
                bookmark["service_md_id"] = bookmark["md_id"]
                # thinking I could maybe 'fix' the settings I thought to get the fav_layer_index here, BUT
                # not possible because that function itself calls layer_equals_fav_layer => too much recursion
                # log.debug(f'fav_layer index?: {self.get_fav_layer_index(fav_lyr)}')
            else:
                # unable to 'fix' ...
                return False
        if (
            bookmark["service_md_id"] == lyr["service_md_id"]
            and bookmark["name"] == lyr["name"]
        ):
            # WMS layer with style
            if "style" in bookmark and "style" in lyr:
                if bookmark["style"] == lyr["style"]:
                    return True
                else:
                    return False
            # other layer without style (but with matching layername and service_md_id)
            return True
        return False

    def delete_bookmark(self, bookmark):

        bookmarks = self.get_bookmarks()
        nr_of_bookmarks = len(bookmarks)

        # find index of fav layer to delete
        bookmark_del_index = self.get_bookmark_index(bookmark)
        # delete fav layer if bookmark
        if bookmark_del_index != -1:
            del bookmarks[bookmark_del_index]
            # overwrite remaining favs from start to end and remove last
            # remaining fav
            self.store_bookmarks(bookmarks)
            # TODO: verwijder overtollige bookmarks in store_bookmarks method
            self.settings_manager.delete_setting(f"favourite_{nr_of_bookmarks}")

    def pdok_layer_in_bookmarks(self, lyr):
        def predicate(x):
            return self.bookmarks_equal(lyr, x)

        fav_layers = self.get_bookmarks()
        i = next((i for i, v in enumerate(fav_layers) if predicate(v)), -1)
        return i

    def move_item_in_list(self, the_list, index, direction):
        if not direction in [1, -1]:
            raise ValueError()
        if index <= 0 and direction == -1:
            return the_list
        if index >= len(the_list) - 1 and direction == 1:
            return the_list
        pos1 = index
        pos2 = index + (direction)
        the_list[pos1], the_list[pos2] = the_list[pos2], the_list[pos1]
        return the_list

    def store_bookmarks(self, bookmarks):
        for i in range(0, len(bookmarks)):
            bookmark_to_store = bookmarks[i]
            self.settings_manager.store_setting(f"favourite_{i+1}", bookmark_to_store)

    def change_bookmark_index(self, bookmark, index_delta):
        bookmark_index = self.get_bookmark_index(bookmark)
        if bookmark_index != -1:
            stored_bookmarks = self.move_item_in_list(
                stored_bookmarks, bookmark_index, index_delta
            )
            self.store_bookmarks(stored_bookmarks)
