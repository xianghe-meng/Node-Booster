# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

import os
import re
import traceback

from .. import get_addon_prefs


def is_float_compatible(string):
    """ check if a string can be converted to a float value"""

    assert type(string) is str
    if (string[0]=='.'):
        return False
    try:
        float(string)
        return True
    except (ValueError, TypeError):
        return False


def match_exact_tokens(string:str, tokenlist:list) -> list:
    """
    Get a list of matching token, if any token in our token list match in our string list

    A token is matched exactly:
      - For numbers (integer/float), it won't match if the token is part of a larger number.
      - For alphabetic tokens, word boundaries are used.
    """
    def build_token_pattern(tokens):
        def boundary(token):
            # For numbers, ensure the token isn't part of a larger number.
            if re.fullmatch(r'\d+(?:\.\d+)?', token):
                return r'(?<![\d.])' + re.escape(token) + r'(?![\d.])'
            else:
                # For alphabetic tokens, use word boundaries.
                return r'\b' + re.escape(token) + r'\b'
        return '|'.join(boundary(token) for token in tokens)
    
    pattern = build_token_pattern(tokenlist)
    return re.findall(pattern, string)


def replace_exact_tokens(string:str, tokens_mapping:dict) -> str:
    """Replace any token in the given string with new values as defined by the tokens_mapping dictionary."""
    
    def build_token_pattern(tokens):
        def boundary(token):
            # If token is a number (integer or float)
            if re.fullmatch(r'\d+(?:\.\d+)?', token):
                # Use negative lookbehind and lookahead to ensure the token isn't part of a larger number.
                return r'(?<![\d.])' + re.escape(token) + r'(?![\d.])'
            else:
                # For alphabetic tokens, use word boundaries.
                return r'\b' + re.escape(token) + r'\b'
        # Build the overall pattern by joining each token pattern with '|'
        return '|'.join(boundary(token) for token in tokens)

    pattern = build_token_pattern(tokens_mapping.keys())
    
    def repl(match):
        token = match.group(0)
        return tokens_mapping.get(token, token)
    
    return re.sub(pattern, repl, string)


def word_wrap(string="", layout=None, alignment="CENTER", max_char=70, char_auto_sidepadding=1.0, context=None, active=False, alert=False, icon=None, scale_y=1.0,):
    """word wrap a piece of string on a ui layout""" 
    
    if ((max_char=='auto') and (context is not None)):
        
        charw = 6.0 # pixel width of a single char
        adjst = 35 # adjustment required
        totpixw = context.region.width * char_auto_sidepadding
        uifac = context.preferences.system.ui_scale
        max_char = ((totpixw/uifac)-adjst)/charw
    
    #adjust user preferences
    sett_plugin = get_addon_prefs()
    max_char = int(max_char * sett_plugin.ui_word_wrap_max_char_factor)
    scale_y = sett_plugin.ui_word_wrap_y * scale_y
    
    def wrap(string,max_char):
        """word wrap function""" 

        original_string = string
        newstring = ""
        
        while (len(string) > max_char):

            # find position of nearest whitespace char to the left of "width"
            marker = max_char - 1
            while (marker >= 0 and not string[marker].isspace()):
                marker = marker - 1

            # If no space was found, just split at max_char
            if (marker==-1):
                marker = max_char
    
            # remove line from original string and add it to the new string
            newline = string[0:marker] + "\n"
            newstring = newstring + newline
            string = string[marker + 1:]

        return newstring + string

    #Multiline string? 
    if ("\n" in string):
          wrapped = "\n".join([wrap(l,max_char) for l in string.split("\n")])
    else: wrapped = wrap(string,max_char)

    #UI Layout Draw? 
    if (layout is not None):

        lbl = layout.column()
        lbl.active = active 
        lbl.alert = alert
        lbl.scale_y = scale_y

        for i,l in enumerate(wrapped.split("\n")):

            if (l=='*SEPARATOR_LINE*'):
                lbl.separator(type='LINE')
                continue

            if (alignment):
                  line = lbl.row()
                  line.alignment = alignment
            else: line = lbl

            if (icon and (i==0)):
                line.label(text=l, icon=icon)    
                continue

            line.label(text=l)
            continue 
    
    return wrapped


def prettyError(e: BaseException, userfilename='',):
    """
    Return a multiline string describing the given exception `e` in a
    more readable format. If it's a SyntaxError, includes line text
    with a caret at the .offset. Otherwise, falls back to the last
    traceback frame and includes the file name, line, and code snippet.
    """

    etypename = type(e).__name__
    
    match etypename:
        
        #Synthax error?
        case 'SyntaxError':
            # e.text is the source line, e.offset is the column offset (1-based)
            # e.lineno is line number, e.filename is file name, e.msg is short message
            faulty_line = e.text or ""
            faulty_line = faulty_line.rstrip("\n")

            # offset can be None or out-of-range
            offset = e.offset or 1
            if offset < 1:
                offset = 1
            if offset > len(faulty_line):
                offset = len(faulty_line)

            highlight = ""
            if (faulty_line):
                highlight = " " * (offset - 1) + "^"*5

            full_error = (
                f"{type(e).__name__}: {e.msg}\n"
                f"File '{e.filename}' At line {e.lineno}.\n"
                f"    {faulty_line}\n"
                f"    {highlight}"
                )
            small_error = (
                f"PythonSynthaxError. {e.msg}. Line {e.lineno}."
                )
            return full_error, small_error

        #Nex Error?
        case 'NexError':

            tb = e.__traceback__
            filtered_tb = tb
            faultyfilename = 'Unknown'
            faultyline = 'Unknown'

            while (filtered_tb is not None):
                # Extract a 1-frame summary for the current node in the traceback
                frame_summaries = traceback.extract_tb(filtered_tb, limit=1)
                if (not frame_summaries):
                    # Something went wrong or we reached the end
                    break

                frame_info = frame_summaries[0]  # A FrameSummary object

                filename = frame_info.filename
                lineno = frame_info.lineno

                if (userfilename in filename):
                    faultyline = lineno
                    faultyfilename = filename
                    break

                filtered_tb = filtered_tb.tb_next
                continue

            full_error = (
                f"NexError: {e}\n"
                f"File '{faultyfilename}' At line {faultyline}.\n"
                )
            small_error = (
                f"{e} Line {faultyline}."
                )
            return full_error, small_error

        # Other exceptions
        case _:

            # We'll extract the traceback frames. The last frame is typically where
            # the exception occurred. We can show file, line, and snippet if available.
            frames = traceback.extract_tb(e.__traceback__)
            if not frames:
                # If there's no traceback info at all, just show type + message
                return f"{type(e).__name__}: {e}", f"{type(e).__name__}. {e}"

            # The last frame is typically the innermost call where the error happened
            last_frame = frames[-1]
            filename = last_frame.filename
            lineno = last_frame.lineno
            code_line = last_frame.line or ""

            if (filename == userfilename):
                full_error = (
                    f"UserSideError. {type(e).__name__}: {e}\n"
                    f"File \"{filename}\", At line {lineno}\n\n"
                    f"    {code_line}"
                    )
                small_error = (
                    f"{type(e).__name__}. {e} Line {lineno}."
                    )
                return full_error, small_error
            
            full_error = (
                f"InternalError. Please report! {type(e).__name__}: {e}\n"
                f"File \"{filename}\", At line {lineno}\n\n"
                f"    {code_line}"
                )
            small_error = (
                f"InternalError. {type(e).__name__}. {e}. File '{os.path.basename(filename)}' line {lineno}."
                )
            return full_error, small_error
