# coding: utf-8

# ISSUES
# - editor doesn't scroll when selection changes
# - repeat view too tall, even hiding title bar

from collections import deque
import plistlib
import re
import sys
import ui
import console
import editor

# how many previous searches do we want to save?
HISTORY_LIMIT = 10

class FindObject(object):
    
    def __init__(self):
        # set up default settings
        self.use_regex = True
        self.case_sensitive = False
        self.selection_only = False
        self.find_text = ''
        self.replace_text = ''
        # load in settings from previous HISTORY_LIMIT searches
        self.history = deque(maxlen=HISTORY_LIMIT)
        self.load_history()
        self.history_idx = 0
        # default to most recent search
        self.use_saved_settings(self.history_idx)
        # set up some housekeeping vars
        self.find_flags = 0
        self.start_offset = 0
        # new_search determines if a find action continues
        #  using the values of the previous find action
        #  or if we have new values
        self.new_search = False
        
    def load_history(self):
        """reads previously saved settings from a plist file"""
        # try to read a plist of previous search values
        try:
            hist = plistlib.readPlist('find_history.pl')
            self.history = deque(hist, maxlen=HISTORY_LIMIT)
        except:
            # we failed, so just keep using the initial defaults
            pass
            
    def use_saved_settings(self, idx):
        """load in settings from a previously saved search"""
        try:
            settings = self.history[idx]
            self.use_regex = settings['use_regex']
            self.case_sensitive = settings['case_sensitive']
            self.selection_only = settings['selection_only']
            self.find_text = settings['find_text']
            self.replace_text = settings['replace_text']
        except:
            # keep current settings
            pass
        
    def store_find_settings(self):
        """saves the most recent search criteria into a plist"""
        # create a dict of the current settings
        cur_settings = {'use_regex': self.use_regex,
                        'case_sensitive': self.case_sensitive,
                        'selection_only': self.selection_only,
                        'find_text': self.find_text,
                        'replace_text': self.replace_text}
        # if these settings already exist in the history file
        #  remove them
        try:
            self.history.remove(cur_settings)
        except:
            # no big deal if they don't
            pass
        # add settings to left end of history
        self.history.appendleft(cur_settings)
        plistlib.writePlist(list(self.history), 'find_history.pl')
        
    def do_find_action(self, sender):
        """builds search criteria from view values and then calls the search methods"""
        self.find_text = sender.superview['find_text'].text
        self.replace_text = sender.superview['replace_text'].text
        # use regular expressions or literal?
        if not self.use_regex:
            self.find_text = re.escape(self.find_text)
        # do we care about case?
        self.find_flags = re.MULTILINE | (0 if self.case_sensitive else re.IGNORECASE)
        # hide dialog
        sender.superview.close()
        # store current settings
        self.store_find_settings()
        # now perform our action
        getattr(self, sender.name)()
        # we want to keep this criteria for next time
        self.new_search = False
        if sender.name in ('find_next', 'find_previous'):
            self.present_repeat_view()
            
    def present_repeat_view(self):
        """shows an abbreviated forward/backward UI for cycling through results"""
        repeat_view = ui.View()
        repeat_view.name = 'FindNextPrev'
        repeat_view.background_color = 'white'
        repeat_view.height = 45
        repeat_view.width = 124
        prev = ui.Button(frame=(6, 6, 32, 32), flex='LT', name='find_previous')
        prev.tint_color = '#007AFF'
        prev.image = ui.Image.named('ionicons-ios7-arrow-up-32')
        prev.action = self.repeat_find_action
        repeat_view.add_subview(prev)
        next = ui.Button(frame=(46, 6, 32, 32), flex='LT', name='find_next')
        next.tint_color = '#007AFF'
        next.image = ui.Image.named('ionicons-ios7-arrow-down-32')
        next.action = self.repeat_find_action
        repeat_view.add_subview(next)
        close = ui.Button(frame=(86, 6, 32, 32), flex='LT', name='close')
        close.tint_color = '#007AFF'
        close.image = ui.Image.named('ionicons-ios7-close-outline-32')
        close.action = self.close_repeat_view
        repeat_view.add_subview(close)
        repeat_view.present('popover', hide_title_bar=True)
    
    def close_repeat_view(self, sender):
        """tells repeat view to close itself"""
        sender.superview.close()

    def repeat_find_action(self, sender):
        """performs a simple forward or backward search using the current criteria"""
        getattr(self, sender.name)()
        
    def find_next(self):
        """performs a simple search"""
        target_text = editor.get_text()
        sel = editor.get_selection()
        # this is the point in the editor where we start from
        self.start_offset = sel[0]
        # if we only want to search the current selection
        #  and the current selection is not an insertion point
        if self.selection_only and sel[0] != sel[1]:
            # then set the target text to the selected text
            target_text = target_text[sel[0]:sel[1]]
        else:
            # if this is the first time we're using these
            #  particular criteria
            if self.new_search:
                # then start our search from the beginning
                #  of the current selection
                target_text = target_text[sel[0]:]
            else:
                # else we are continuing a previous search
                #  and we need to start from the end of the
                #  current selection
                self.start_offset = sel[1]+1
                target_text = target_text[self.start_offset:]
        # do the search
        res = re.search(self.find_text, target_text, flags=self.find_flags)
        if res:
            # since res.start/end is relative to the string we searched
            #  rather than the entire editor, we have to add back in
            #  the offset we stored earlier
            editor.set_selection(self.start_offset + res.start(), self.start_offset + res.end())
            # we want to reuse this criteria next time
            self.new_search = False
            return True
        else:
            console.hud_alert('not found', 'error')
            return False
    
    def find_previous(self):
        """performs a simple search in reverse"""
        target_text = editor.get_text()
        sel = editor.get_selection()
        # if we only want to search the current selection
        #  and the current selection is not an insertion point
        if self.selection_only and sel[0] != sel[1]:
            # store our starting point
            self.start_offset = sel[0]
            # then set the target text to the selected text
            target_text = target_text[sel[0]:sel[1]]
        else:
            # set the starting offset to the top of the editor
            self.start_offset = 0
            # if this is the first time we're using these
            #  particular criteria
            if self.new_search:
                # then our search goes to the end of the
                #  current selection
                target_text = target_text[:sel[1]]
            else:
                # then our search stops at the start of the
                #  current selection
                target_text = target_text[:sel[0]]
        # do the search
        # this actually returns all of the hits
        res = re.finditer(self.find_text, target_text, flags=self.find_flags)
        # what we get back is an iterator, so convert it to a list
        res = list(res)
        # if we have any results...
        if res:
            # ...take the last one
            res = res[-1]
            # since res.start/end is relative to the string we searched
            #  rather than the entire editor, we have to add back in
            #  the offset we stored earlier
            editor.set_selection(self.start_offset + res.start(), self.start_offset + res.end())
            # we want to reuse this criteria next time
            self.new_search = False
            return True
        else:
            console.hud_alert('not found', 'error')
            return False
            
    def replace_all(self):
        """replaces all occurrences of find_text"""
        target_text = editor.get_text()
        sel = editor.get_selection()
        cnt = 0
        # if we only want to search the current selection
        #  and the current selection is not an insertion point
        if self.selection_only and sel[0] != sel[1]:
            # then set the target text to the selected text
            target_text = target_text[sel[0]:sel[1]]
            # and it's simply a matter of doing the replacement
            res = re.subn(self.find_text, self.replace_text, target_text, flags=self.find_flags)
            # re.subn returns a tuple (new_string, number_of_subs_made)
            if res[1] > 0:
                editor.replace_text(sel[0], sel[1], res[0])
                cnt += res[1]
        else:
            # We split the text in two at the selection
            #  and perform the replacement on both halves
            #  separately so that we can maintain the same
            #  selection point once we have done the replacement.
            # This accounts for changes in the size of the preceding
            #  text without having to calculate string length
            #  differences and such.
            top_half = target_text[:sel[0]]
            bottom_half = target_text[sel[0]:]
            new_text = ''
            for _ in (top_half, bottom_half):
                res = re.subn(self.find_text, self.replace_text, _, flags=self.find_flags)
                new_text += res[0]
                cnt += res[1]
            editor.replace_text(0, len(target_text), new_text)
            editor.set_selection(len(top_half), len(top_half))
        # display number of replacements
        console.hud_alert('{} replacement{} made'.format(cnt, '' if cnt == 1 else 's'),
                            icon='success' if cnt > 0 else 'error', duration = 2)
    
    def replace_and_find(self):
        """performs a replace action then searchs for find_text again"""
        sel = editor.get_selection()
        # first we need to check if the string we're searching for
        #  is currently selected
        # if it is, we will simply replace it and look for the next
        # if it isn't, we need to find the next one, replace it and then
        #  look for the one after that
        # so that replace_and_find always starts out with a replace
        target_text = editor.get_text()[sel[0]:sel[1]]
        if target_text == self.find_text:
            # we already have an instance of the find_text
            #  so replace it
            editor.replace_text(sel[0], sel[1], self.replace_text)
        else:
            # we need to find the next instance of the find text...
            self.find_next()
            #  ...and then replace it
            sel = editor.get_selection()
            editor.replace_text(sel[0], sel[1], self.replace_text)
        # now find the next one
        self.find_next()
        
    def set_attr(self, ctrl):
        """sets one piece of the search criteria"""
        setattr(self, ctrl.name, ctrl.value)
        # invalidate the current search
        self.new_search = True
    
    def textview_did_change(self, textview):
        """delegate method for TextView"""
        # we have changed either find_text or replace_text
        #  and so we will start a new find action the next
        #  time we hit a button
        self.new_search = True
    
    def textview_should_change(self, textview, range, replacement):
        """delegate method for TextView"""
        # block tabs from being entered into the textview
        #  and use them to switch to the other textview
        if replacement == '\t':
            if textview.name == 'find_text':
                textview.superview['replace_text'].begin_editing()
            else:
                textview.superview['find_text'].begin_editing()
            return False
        else:
            # everything else gets passed through to the textview
            return True
        
    def update_search_settings(self, sender):
        """cycle through our history items and load the values into the view"""
        # first determine which direction...
        self.history_idx += 1 if sender.name == 'history_previous' else -1
        # ...grab the saved settings...
        self.use_saved_settings(self.history_idx)
        # ...and then load 'em up
        sender.superview['use_regex'].value = self.use_regex
        sender.superview['case_sensitive'].value = self.case_sensitive
        sender.superview['selection_only'].value = self.selection_only
        sender.superview['find_text'].text = self.find_text
        sender.superview['replace_text'].text = self.replace_text
        # enable/disable the history buttons if we are at the
        #  beginning or end of the history list
        sender.superview['history_next'].enabled = False if self.history_idx == 0 else True
        sender.superview['history_previous'].enabled = False if self.history_idx == len(self.history)-1 else True
        
def main():
    find = FindObject()
    view = ui.load_view('FindAndReplace')
    # set default values for switches and textviews
    view['use_regex'].value = find.use_regex
    view['case_sensitive'].value = find.case_sensitive
    view['selection_only'].value = find.selection_only
    view['find_text'].text = find.find_text
    view['replace_text'].text = find.replace_text
    # hook up our action handlers
    view['use_regex'].action = find.set_attr
    view['case_sensitive'].action = find.set_attr
    view['selection_only'].action = find.set_attr
    view['find_next'].action = find.do_find_action
    view['find_previous'].action = find.do_find_action
    view['replace_and_find'].action = find.do_find_action
    view['replace_all'].action = find.do_find_action
    view['history_next'].action = find.update_search_settings
    view['history_previous'].action = find.update_search_settings
    view['history_next'].enabled = False
    # hook up our find object as delegate to the textviews
    view['find_text'].delegate = find
    view['replace_text'].delegate = find
    view['find_text'].begin_editing()
    # now show the thing
    view.present('popover')
    
if __name__ == '__main__':
    main()
