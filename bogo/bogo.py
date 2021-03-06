#
# This file is part of ibus-bogo project.
#
# Copyright (C) 2012 Long T. Dam <longdt90@gmail.com>
# Copyright (C) 2012-2013 Trung Ngo <ndtrung4419@gmail.com>
# Copyright (C) 2013 Duong H. Nguyen <cmpitg@gmail.com>
#
# ibus-bogo is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ibus-bogo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ibus-bogo.  If not, see <http://www.gnu.org/licenses/>.
#

from .valid_vietnamese import is_valid_combination
from . import utils, accent, mark
import logging
import copy


Mark = mark.Mark
Accent = accent.Accent


class Action:
    UNDO = 3
    ADD_MARK = 2
    ADD_ACCENT = 1
    ADD_CHAR = 0


default_config = {
    "input-method": "telex",
    "output-charset": "utf-8",
    "skip-non-vietnamese": True,
    "enable-text-expansion": False,
    "auto-capitalize-expansion": False,
    "default-input-methods": {
        "simple-telex": {
            "a": "a^",
            "o": "o^",
            "e": "e^",
            "w": ["u*", "o*", "a+"],
            "d": "d-",
            "f": "\\",
            "s": "/",
            "r": "?",
            "x": "~",
            "j": "."
        },
        "telex": {
            "a": "a^",
            "o": "o^",
            "e": "e^",
            "w": ["u*", "o*", "a+", "<ư"],
            "d": "d-",
            "f": "\\",
            "s": "/",
            "r": "?",
            "x": "~",
            "j": ".",
            "]": "<ư",
            "[": "<ơ",
            "}": "<Ư",
            "{": "<Ơ"
        },
        "vni": {
            "6": ["a^", "o^", "e^"],
            "7": ["u*", "o*"],
            "8": "a+",
            "9": "d-",
            "2": "\\",
            "1": "/",
            "3": "?",
            "4": "~",
            "5": "."
        }
    }
}


def get_default_config():
    return copy.deepcopy(default_config)


def is_processable(comps):
    # For now only check the last 2 components
    return is_valid_combination(('', comps[1], comps[2]), final_form=False)


def process_key(string, key, fallback_sequence="", config=None):
    """
    Try to apply the transformations inferred from `key` to `string` with
    `fallback_sequence` as a reference. `config` should be a dictionary-like
    object following the form of `default_config`.

    returns (new string, new fallback_sequence)

    >>> process_key('a', 'a', 'a')
    (â, aa)

    Note that when a key is an undo key, it won't get appended to
    `fallback_sequence`.

    >>> process_key('â', 'a', 'aa')
    (aa, aa)
    """
    # TODO Figure out a way to remove the `string` argument. Perhaps only the
    #      key sequence is needed?
    logging.debug("== In process_key() ==")
    logging.debug("key = %s", key)
    logging.debug("string = %s", string)
    logging.debug("fallback_sequence = %s", fallback_sequence)

    def default_return():
        return string + key, fallback_sequence + key

    # Let's be extra-safe
    if config is None:
        config = default_config
    else:
        tmp = config
        config = default_config.copy()
        config.update(tmp)  # OMG, Python's dict.update is IN-PLACE!

    # Get the input method translation table (Telex, VNI,...)
    if config["input-method"] in config["default-input-methods"]:
        im = config["default-input-methods"][config["input-method"]]
    elif "custom-input-methods" in config and \
            config["input-method"] in config["custom-input-methods"]:
        im = config["custom-input-methods"][config["input-method"]]

    comps = utils.separate(string)
    logging.debug("separate(string) = %s", str(comps))

    # if not is_processable(comps):
    #     return default_return()

    # Find all possible transformations this keypress can generate
    trans_list = get_transformation_list(key, im, fallback_sequence)
    logging.debug("trans_list = %s", trans_list)

    # Then apply them one by one
    new_comps = list(comps)
    for trans in trans_list:
        new_comps = transform(new_comps, trans)

    logging.debug("new_comps: %s", str(new_comps))
    if new_comps == comps:
        tmp = list(new_comps)

        # If none of the transformations (if any) work
        # then this keystroke is probably an undo key.
        if can_undo(new_comps, trans_list):
            # The prefix "_" means undo.
            for trans in map(lambda x: "_" + x, trans_list):
                new_comps = transform(new_comps, trans)

            # TODO refactor
            if config["input-method"] == "telex" and \
                    len(fallback_sequence) >= 1 and \
                    new_comps[1] and new_comps[1][-1].lower() == "u" and \
                    (fallback_sequence[-1:]+key).lower() == "ww" and \
                    not (len(fallback_sequence) >= 2 and
                         fallback_sequence[-2].lower() == "u"):
                new_comps[1] = new_comps[1][:-1]

        if tmp == new_comps:
            fallback_sequence += key
        new_comps = utils.append_comps(new_comps, key)
    else:
        fallback_sequence += key

    if config['skip-non-vietnamese'] is True and key.isalpha() and \
            not is_valid_combination(new_comps, final_form=False):
        result = fallback_sequence, fallback_sequence
    else:
        result = utils.join(new_comps), fallback_sequence

    logging.debug("Final word: %s, %s", result[0], result[1])
    return result


def get_transformation_list(key, im, fallback_sequence):
    """
        Return the list of transformations inferred from the entered key. The
        map between transform types and keys is given by module
        bogo_config (if exists) or by variable simple_telex_im

        if entered key is not in im, return "+key", meaning appending
        the entered key to current text
    """
    # if key in im:
    #     lkey = key
    # else:
    #     lkey = key.lower()
    lkey = key.lower()

    if lkey in im:
        if isinstance(im[lkey], list):
            trans_list = im[lkey]
        else:
            trans_list = [im[lkey]]

        for i, trans in enumerate(trans_list):
            if trans[0] == '<' and key.isalpha():
                trans_list[i] = trans[0] + utils.change_case(trans[1],
                                                             int(key.isupper()))

        if trans_list == ['_']:
            if len(fallback_sequence) >= 2:
                # TODO Use takewhile()/dropwhile() to process the last IM keypress
                # instead of assuming it's the last key in fallback_sequence.
                t = list(map(lambda x: "_" + x,
                             get_transformation_list(fallback_sequence[-2], im,
                                                     fallback_sequence[:-1])))
                # print(t)
                trans_list = t
            # else:
            #     trans_list = ['+' + key]

        return trans_list
    else:
        return ['+' + key]


def get_action(trans):
    """
    Return the action inferred from the transformation `trans`.
    and the parameter going with this action
    An Action.ADD_MARK goes with a Mark
    while an Action.ADD_ACCENT goes with an Accent
    """
    # TODO: VIQR-like convention
    if trans[0] in ('<', '+'):
        return Action.ADD_CHAR, trans[1]
    if trans[0] == "_":
        return Action.UNDO, trans[1:]
    if len(trans) == 2:
        if trans[1] == '^':
            return Action.ADD_MARK, Mark.HAT
        if trans[1] == '+':
            return Action.ADD_MARK, Mark.BREVE
        if trans[1] == '*':
            return Action.ADD_MARK, Mark.HORN
        if trans[1] == "-":
            return Action.ADD_MARK, Mark.BAR
        # if trans[1] == "_":
        #     return Action.ADD_MARK, Mark.NONE
    else:
        if trans[0] == "\\":
            return Action.ADD_ACCENT, Accent.GRAVE
        if trans[0] == "/":
            return Action.ADD_ACCENT, Accent.ACUTE
        if trans[0] == "?":
            return Action.ADD_ACCENT, Accent.HOOK
        if trans[0] == "~":
            return Action.ADD_ACCENT, Accent.TIDLE
        if trans[0] == ".":
            return Action.ADD_ACCENT, Accent.DOT
        # if trans[0] == "_":
        #     return Action.ADD_ACCENT, Accent.NONE


def transform(comps, trans):
    """
    Transform the given string with transform type trans
    """
    logging.debug("== In transform(%s, %s) ==", comps, trans)
    components = list(comps)

    action, parameter = get_action(trans)
    if action == Action.ADD_MARK and \
            components[2] == "" and \
            mark.strip(components[1]).lower() in ['oe', 'oa'] and trans == "o^":
        action, parameter = Action.ADD_CHAR, trans[0]

    if action == Action.ADD_ACCENT:
        components = accent.add_accent(components, parameter)
    elif action == Action.ADD_MARK and mark.is_valid_mark(components, trans):
        components = mark.add_mark(components, parameter)

        # Handle uơ in "huơ", "thuở", "quở"
        # If the current word has no last consonant and the first consonant
        # is one of "h", "th" and the vowel is "ươ" then change the vowel into
        # "uơ", keeping case and accent. If an alphabet character is then added
        # into the word then change back to "ươ".
        #
        # NOTE: In the dictionary, these are the only words having this strange
        # vowel so we don't need to worry about other cases.
        if accent.remove_accent_string(components[1]).lower() == "ươ" and \
                not components[2] and components[0].lower() in ["", "h", "th", "kh"]:
            # Backup accents
            ac = accent.get_accent_string(components[1])
            components[1] = ('u', 'U')[components[1][0].isupper()] + components[1][1]
            components = accent.add_accent(components, ac)

    elif action == Action.ADD_CHAR:
        if trans[0] == "<":
            if not components[2]:
                # Only allow ư, ơ or ươ sitting alone in the middle part
                # and ['g', 'i', '']. If we want to type giowf = 'giờ', separate()
                # will create ['g', 'i', '']. Therefore we have to allow
                # components[1] == 'i'.
                if (components[0].lower(), components[1].lower()) == ('g', 'i'):
                    components[0] += components[1]
                    components[1] = ''
                if not components[1] or \
                        (components[1].lower(), trans[1].lower()) == ('ư', 'ơ'):
                    components[1] += trans[1]
        else:
            components = utils.append_comps(components, parameter)
            if parameter.isalpha() and \
                    accent.remove_accent_string(components[1]).lower().startswith("uơ"):
                ac = accent.get_accent_string(components[1])
                components[1] = ('ư', 'Ư')[components[1][0].isupper()] + \
                    ('ơ', 'Ơ')[components[1][1].isupper()] + components[1][2:]
                components = accent.add_accent(components, ac)
    elif action == Action.UNDO:
        components = reverse(components, trans[1:])

    if action == Action.ADD_MARK or (action == Action.ADD_CHAR and parameter.isalpha()):
        # If there is any accent, remove and reapply it
        # because it is likely to be misplaced in previous transformations
        ac = accent.get_accent_string(components[1])

        if ac != accent.Accent.NONE:
            components = accent.add_accent(components, Accent.NONE)
            components = accent.add_accent(components, ac)

    logging.debug("After transform: %s", components)
    return components


def reverse(components, trans):
    """
    Reverse the effect of transformation 'trans' on 'components'
    If the transformation does not affect the components, return the original
    string.
    """

    action, parameter = get_action(trans)
    comps = list(components)
    string = utils.join(comps)

    if action == Action.ADD_CHAR and string[-1].lower() == parameter.lower():
        if comps[2]:
            i = 2
        elif comps[1]:
            i = 1
        else:
            i = 0
        comps[i] = comps[i][:-1]
    elif action == Action.ADD_ACCENT:
        comps = accent.add_accent(comps, Accent.NONE)
    elif action == Action.ADD_MARK:
        if parameter == Mark.BAR:
            comps[0] = comps[0][:-1] + \
                mark.add_mark_char(comps[0][-1:], Mark.NONE)
        else:
            if mark.is_valid_mark(comps, trans):
                comps[1] = "".join([mark.add_mark_char(c, Mark.NONE)
                                    for c in comps[1]])
    return comps


def can_undo(comps, trans_list):
    """
    Return whether a components can be undone with one of the transformation in
    trans_list.
    """
    comps = list(comps)
    accent_list = list(map(accent.get_accent_char, comps[1]))
    mark_list = list(map(mark.get_mark_char, utils.join(comps)))
    action_list = list(map(lambda x: get_action(x), trans_list))

    def atomic_check(action):
        """
        Check if the `action` created one of the marks, accents, or characters
        in `comps`.
        """
        return (action[0] == Action.ADD_ACCENT and action[1] in accent_list) \
                or (action[0] == Action.ADD_MARK and action[1] in mark_list) \
                or (action[0] == Action.ADD_CHAR and action[1] == \
                    accent.remove_accent_char(comps[1][-1]))  # ơ, ư

    return any(map(atomic_check, action_list))
