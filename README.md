ISearch: instantly find the relevant text documents
===

## Overview

"ISearch" (or Instant Search) is a search-as-you-type curses based search tool implemented in Python (python3). Search process is significantly simplified with the help of auto-complete suggestions which are generated after analyzing the content (not just the file names) of all the files indexed.

## Skip to:

* [How to install](#how-to-install)
* [Usage](#usage)
* [Implementation](#implementation)
* [Changelog](#changelog)
---

## How to install

    pip install --user metapy autocomplete
    or
    pip install metapy autocomplete (admin rights needed)

## Usage

    $ python3 isearch.py <reload> <directory path to text files>

Passing in the "reload" option forces rebuilding of index and retraining of autocomplete's predictive model. Index building and re-training auto-complete model could take some time if the number of text
files are huge. If no files are changed in the text file directory, there is no need pass in
the "reload" option. The program will simply use the existing index and already trained model.

By default the program looks for text and PDF files in dataset/files directory but user
can specify the program to look for text files in a different directory. Naturally, "reload"
option must be used when a new directory is specified.

Your search will start immediately as you type at the search prompt. When there are
auto-complete suggestions available, a list of suggestions will be shown below the search
string. You can use up/down arrow key to select one of the auto-complete suggestions and
hit ENTER key to confirm.

When there are more than one file matching the search string, a list of matching files will
appear near the top right of the screen. You can use left/right arrow key to cycle through
all the matched files to see the lines in a file that contain the search string.

Press Ctrl-C anytime to exist the program.

## Implementation

This python program make use of two other python packages namely the python bindings for MeTA (ModErn Text Analysis) ([metapy]) and Autocomplete ([autocomplete]). When the program starts, all the files inside the default directory (dataset/files/) or the user specified directory will be processed. If pdf-to-text file tool "pdftotext" is available on the system, PDF files in the directory will be automatically converted to plain text file so they can be indexed as well. After all the text files are indexed, autocomplete toolkit will be used to analyze all the contents in those files and generate a predictive model which will be used to provide autocomplete suggestion as user starts typing their search key word.

To facilitate user input and display of autocomplete suggestions and search results, curses interface is used. After files are indexed and predictive model is generated, a search prompt will be presented at the top of the screen waiting for user input. Everytime user type a character or erase a character, autocomplete predictive model will be used to re-generate a list of possible search words (if any). For example, since the default list of text files include a story about Sherlock Holmes, when a user type in "sher", "sherlock", "sherry" and "sherbet" will be presented in the autocomplete suggestion list.

The "instant" part of the instant search comes from the fact that search is performed everytime the search string is changed (i.e. either a character is add, removed or an autocomplete suggestion is applied). metapy is used to perform such search by using the search string. Search-as-you-type mechanism helps users to get instant feedback on their search string (even if it is only partially completed).

#### Limitations:
Scaling is one of the issues with this program. The more text documents need to be parsed, the more time will be needed to parse, index and create the predicitive model. With the default sample of 11 text files, there are a total of 945280 words which take about 4 seconds to index and to create the predictive model. On the positive side, index and model creation only need to be done once. As long as the files involved don't change, there is no need to re-index or re-generate the predicitive model.

Another limitation comes from the fact that autocomplete toolkit currently only supports generating suggestion up to two words. More work will need to be done on the autocomplete implementation itself in order to expand on its capabilities.

Presentation of the result can also be improved. Curses based presentation can be limited by the dimension of user's terminal. A typical terminal size is only 80x24 which does not give a lot of room to display autocomplete suggestions, search results and matching file content on the same screen. Web-based implementation of the isearch would likely help to minimize some of these problems.

## Changelog
* 8-Dec-2018 initial version

[metapy]: https://github.com/meta-toolkit/metapy
[autocomplete]: https://github.com/rodricios/autocomplete
