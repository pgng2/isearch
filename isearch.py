# A simple curses-based search-as-you-type search tool that includes
# auto-complete feature to improve usability.
#
# Usage:
#    python3 isearch.py <reload> <directory path to text files>

import metapy
import pytoml
import math
import sys, termios, tty, os, time
import autocomplete
import subprocess
import curses
import os
import re
from curses import wrapper

iidx = None
ranker = None

autocomplete_model = 'models_compressed.pkl'

# Find the full path of a system command
# Return None if the system command is not found
def which(executable):
    for path in os.environ["PATH"].split(os.pathsep):
        file_path = os.path.join(path, executable)
        if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
            return file_path
    return None



# Use "pdftotext" command to convert a pdf file to a plain text file
# Return True if conversion is successful, otherwise return False
def convert_pdf_to_txt(pdf_file_path):
    pdftotext_cmd = which('pdftotext')
    if None == pdftotext_cmd:
        return False

    cmd = [ pdftotext_cmd, pdf_file_path ]
    try:
        subprocess.check_call(cmd)
    except:
        return False

    return True



# Convert all the PDF files inside the specified directory into text files
# PDF files will be converted to txt files if the program
# "pdftotext" is installed.
def process_pdf(dir_path):
    for f in os.listdir(dir_path):
        isPdfFile = re.compile('(.*)\.pdf').match(f)
        if isPdfFile:
            processed = os.path.exists(os.path.join(dir_path, isPdfFile.group(1)+'.txt'))
            if processed:
                continue
            else:
                convert_pdf_to_txt(os.path.join(dir_path,f))



# Determine if a file is "text" file
def isTextFile(file_path):
    isText = False
    file_cmd = which('file') # use the 'file command if available
    if None == file_cmd:
        isText = re.compile('(.*)\.txt').match(file_path) != None
    else:
        result = subprocess.Popen([ file_cmd, file_path ], stdout=subprocess.PIPE).stdout.read()
        isText = re.compile('.*:.* text').match(result.decode().rstrip()) != None
    return isText




# Update the full-corpus.txt file
def update_corpus_file(dataset_path, files_path):
    corpus_file = open(dataset_path+'files-full-corpus.txt', 'w+')

    for f in os.listdir(files_path):
        if isTextFile(os.path.join(files_path, f)):
            corpus_file.write('None '+os.path.relpath(files_path, dataset_path)+'/'+f+'\n')

    corpus_file.close()


# Create auto-complete model based on the inverted index
def train_autocomplete_model(iidx):
    model_file = './'+autocomplete_model

    if os.path.isfile(model_file):
        autocomplete.models.load_models(model_file)
        return

    data = ''
    for doc_id in iidx.docs():
        filename = iidx.metadata(doc_id).get('path')
        fpath = os.path.join(os.path.dirname(__file__), filename)
        with open(fpath, 'r') as f:
            data = data + ' ' +str(f.read())

    autocomplete.models.train_models(data, '')
    autocomplete.models.save_models(model_file)
    autocomplete.models.load_models(model_file)



# Get a list of auto-complete suggestions for the specified string
def get_ac_list(str, count):
    ac_list = []

    words = str.split()

    # Note that the auto-complete library only supports up to two full words
    if len(words) > 2:
        return ac_list

    if len(words) > 1:
        try:
            l = autocomplete.predict(words[0], words[1], count)
            for name,num in l:
                ac_list.append(words[0]+' '+name)
        except:
            # Due to a bug in the auto-complete library,
            # words that contain number (e.g. abcde10) doesn't get
            # handled properly
            return []
    elif len(words) == 1:
        l = autocomplete.predict_currword(words[0], count)
        for name,num in l:
            ac_list.append(name)

    return ac_list



# When trying to display a string that is too long for the user's
# terminal, we put ellipsis to indicate string is truncated
def get_sanitized_string(window_width, s):
    if len(s) > window_width:
        s = s[:window_width-4]+'...'
    return s



# Show the lines in the file that matches the search string
# If there are too many lines to show in the user's terminal,
# we'll use ellipsis to indicate.
def show_file_content(window, file_path, search_string):
    h, w = window.getmaxyx()
    window.clear()
    window.addstr(0, 0, get_sanitized_string(w, file_path), curses.A_BOLD|curses.A_UNDERLINE)
    window.refresh()
    cmd = ['grep', '-i', '-n', search_string.lower(), file_path ]
    try:
        cmd_output = subprocess.check_output(cmd)
        lines = cmd_output.splitlines(True)
        idx = 1
        for line in lines:
            line = line.decode('utf-8').rstrip()
            line = get_sanitized_string(w, line)
            window.addstr(idx, 0, line)
            window.refresh()
            idx = idx + 1
            if idx == h-1:
                window.addstr(idx, 0, '... more ...')
                window.refresh()
                break
    except:
        return



def start_curses(stdscr):
    # Clear screen
    stdscr.clear()
    stdscr.refresh()

    # Minimum window size required for decent display
    height, width = stdscr.getmaxyx()
    if height < 24 or width < 80:
        return

    curses.curs_set(False) # hide the cursor

    # search window
    s_win_x = 0
    s_win_y = 0
    s_win_h = 7
    s_win_w = 30
    s_win = curses.newwin(s_win_h, s_win_w, s_win_y, s_win_x)
    s_cur_x = 0
    s_cur_y = 0 
    search_string = 'Search: '
    s_win.addstr(s_cur_y, s_cur_x, search_string)
    s_win.refresh()
    s_cur_x = s_cur_x + len(search_string)

    # autocomplete window (situated inside search window)
    ac_win_x = len(search_string) 
    ac_win_y = s_cur_y + 1
    ac_win_h = s_win_h - 1  # maximum number of auto-complete suggestions
    ac_win_w = s_win_w - ac_win_x # width of auto-complete suggestions
    ac_win = curses.newwin(ac_win_h, ac_win_w, ac_win_y, ac_win_x)
    ac_win.refresh()
    ac_cur_x = 0
    ac_cur_y = -1

    # list of file(s) matching the search string
    result_win_x = s_win_w
    result_win_y = 0
    result_win_h = 11 
    result_win_w = width - result_win_x
    result_win = curses.newwin(result_win_h, result_win_w, result_win_y, result_win_x)
    result_cur_x = 0
    result_cur_y = 0
    result_string = 'Files:'
    result_win.refresh()

    # file content window
    fc_win_x = 0
    fc_win_y = result_win_h + 1
    fc_win_h = height - fc_win_y
    fc_win_w = width
    fc_win = curses.newwin(fc_win_h, fc_win_w, fc_win_y, fc_win_x)
    fc_cur_x = 0
    fc_cur_y = 0
    fc_win.refresh()

    search_str = ''
    word = ''

    ac_list = []  # list of auto-complete selections
    f_list = []   # list of files matching the search string

    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    while True:
        try:
            c = stdscr.getch()
    
            if c == curses.KEY_BACKSPACE:
                ac_cur_y = -1 # reset the ac_list y cursor

                # update search string
                if len(search_str) > 0:
                    search_str = search_str[:len(search_str)-1]
                s_win.move(s_cur_y, s_cur_x) # set the cursor for next clear operation
                s_win.clrtoeol()
                s_win.addstr(s_cur_y, s_cur_x, search_str)
                s_win.refresh()
    
                # show new auto-complete selections
                ac_win.clear()
                ac_win.refresh()
                ac_list = get_ac_list(search_str.lower(), ac_win_h)
                idx=0
                for s in ac_list:
                    ac_win.addstr(idx, 0, s)
                    ac_win.refresh()
                    idx=idx+1
    
            elif c == curses.KEY_DOWN and len(ac_list) > 0:
                if ac_cur_y < 0:
                    ac_cur_y = 0
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_REVERSE)
                    ac_win.refresh()
                elif ac_cur_y >= len(ac_list)-1:
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_NORMAL)
                    ac_win.refresh()
                    ac_cur_y = -1
                else:
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_NORMAL)
                    ac_cur_y = ac_cur_y + 1
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_REVERSE)
                    ac_win.refresh()
                continue
    
            elif c == curses.KEY_UP and len(ac_list) > 0:
                if ac_cur_y < 0:
                    ac_cur_y = len(ac_list)-1
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_REVERSE)
                    ac_win.refresh()
                elif ac_cur_y == 0:
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_NORMAL)
                    ac_win.refresh()
                    ac_cur_y = -1
                else:
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_NORMAL)
                    ac_cur_y = ac_cur_y - 1
                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_REVERSE)
                    ac_win.refresh()
                continue

            elif c == curses.KEY_LEFT or c == 260:
                n = len(f_list)
                if n > 0:
                    if f_list_idx > 0:
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_NORMAL)
                        f_list_idx = f_list_idx - 1 
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_REVERSE)
                        result_win.refresh()
                    elif f_list_idx == 0:
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_NORMAL)
                        f_list_idx = len(f_list)-1
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_REVERSE)
                        result_win.refresh()

                # show file's content
                show_file_content(fc_win, f_list[f_list_idx], search_str)
                continue

            elif c == curses.KEY_RIGHT or c == 261:
                n = len(f_list)
                if n > 0:
                    if f_list_idx < len(f_list)-1:
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_NORMAL)
                        f_list_idx = f_list_idx + 1 
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_REVERSE)
                        result_win.refresh()
                    elif f_list_idx == len(f_list)-1:
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_NORMAL)
                        f_list_idx = 0
                        file_path = get_sanitized_string(result_win_w, f_list[f_list_idx])
                        result_win.addstr(f_list_idx+1, 0, file_path, curses.A_REVERSE)
                        result_win.refresh()

                # show file's content
                show_file_content(fc_win, f_list[f_list_idx], search_str)
                continue
    
            elif c == curses.KEY_ENTER or c == 10:
                if ac_cur_y >= 0 and ac_cur_y < len(ac_list):
                    # update search string with selected auto-complete option
                    search_str = ac_list[ac_cur_y]
                    s_win.move(s_cur_y, s_cur_x) # set the cursor for next clear operation
                    s_win.clrtoeol()
                    s_win.addstr(s_cur_y, s_cur_x, search_str)
                    s_win.refresh()

                    ac_win.addstr(ac_cur_y, 0, ac_list[ac_cur_y], curses.A_NORMAL)
                    ac_win.clear()
                    ac_win.refresh()
                    ac_cur_y = -1
                    ac_list = []
                else:
                    ac_win.clear()
                    ac_win.refresh()
    
            if c >= 32 and c <= 126: # printable ascii
                ac_cur_y = -1 # reset the ac_list y cursor
                ch = str(chr(c))
                search_str = search_str + ch
    
                s_win.move(s_cur_y, s_cur_x) # set the cursor for next clear operation
                s_win.clrtoeol()
                s_win.addstr(s_cur_y, s_cur_x, search_str)
                s_win.refresh()
    
                ac_win.clear()
                ac_win.refresh()
    
                ac_list = get_ac_list(search_str.lower(), ac_win_h)
                idx=0
                for s in ac_list:
                    ac_win.addstr(idx, 0, s)
                    ac_win.refresh()
                    idx=idx+1
    
            # perform search immeidately
            result_win.clear()
            result_win.refresh()
            fc_win.clear()
            fc_win.refresh()

            query = metapy.index.Document()
            query.content(search_str.lower())
            top_docs = ranker.score(iidx, query, result_win_h-1)

            # display a list of matching files (if any)
            if len(top_docs) > 0:
                result_win.move(0, 0)
                result_win.addstr(0, 0, result_string)
                result_win.refresh()
                f_list = []
                f_list_idx = 0
                fc_win.clear()
                fc_win.refresh()
                idx=1
                for doc in top_docs:
                    file_path = iidx.metadata(doc[0]).get('path')
                    f_list.append(file_path)
                    if len(file_path) > result_win_w:
                        file_path = file_path[:result_win_w-4]+'...'
                    if idx == 1:
                        result_win.addstr(idx, 0, file_path, curses.A_REVERSE)
                    else:
                        result_win.addstr(idx, 0, file_path)
                    result_win.refresh()
                    idx=idx+1

                # show file's content
                show_file_content(fc_win, f_list[f_list_idx], search_str)

        except KeyboardInterrupt as ki:
            # graceful shutdown
            break
                
    stdscr.refresh()

if __name__ == '__main__':
    reload = False
    files_path = os.getcwd()+'/dataset/files/' # default location of users' text files

    if len(sys.argv) > 1 and sys.argv[1] == 'reload':
        reload = True

    if len(sys.argv) > 2:
        files_path = sys.argv[2]

    # We're rebuilding index and autocomplete model
    if reload:
        subprocess.call([ 'rm', '-rf', 'idx'])
        subprocess.call([ 'rm', '-f', autocomplete_model])
        subprocess.call([ 'rm', '-f', 'dataset/files-full-corpus.txt'])

    # Convert all pdf inside the "dataset/files/" directory into
    # plain text file first
    process_pdf(files_path)

    # Update the full-corpus.txt file
    update_corpus_file(os.getcwd()+'/dataset/', files_path)

    iidx = metapy.index.make_inverted_index('config.toml')

    print('Number of documents indexed     =',iidx.num_docs())
    print('Total number of terms in index  =',iidx.total_corpus_terms())
    print('Number of unique terms in index =',iidx.unique_terms())
    print('Average document length         =',iidx.avg_doc_length())
    print()
    if reload:
        print('Training autocomplete model...')
    train_autocomplete_model(iidx)
    if reload:
        print('Done')
    print()

    ranker = metapy.index.OkapiBM25()

    # Sanity check
#    query = metapy.index.Document()
#    query.content('mining')
#    top_docs = ranker.score(iidx, query, num_results=5)
#    if len(top_docs) > 0:
#        print('Search results:')
#    for doc in top_docs:
#        print('File path=',iidx.metadata(doc[0]).get('path'))

    wrapper(start_curses)

    sys.exit(0)
