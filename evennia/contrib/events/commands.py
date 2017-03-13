"""
Module containing the commands of the event system.
"""

from datetime import datetime

from django.conf import settings
from evennia import Command
from evennia.contrib.events.extend import get_event_handler
from evennia.utils.eveditor import EvEditor
from evennia.utils.evtable import EvTable
from evennia.utils.utils import class_from_module, time_format

COMMAND_DEFAULT_CLASS = class_from_module(settings.COMMAND_DEFAULT_CLASS)
COMMAND_DEFAULT_CLASS = class_from_module(settings.COMMAND_DEFAULT_CLASS)

# Permissions
WITH_VALIDATION = getattr(settings, "EVENTS_WITH_VALIDATION", None)
WITHOUT_VALIDATION = getattr(settings, "EVENTS_WITHOUT_VALIDATION",
        "immortals")
VALIDATING = getattr(settings, "EVENTS_VALIDATING", "immortals")

# Split help file
BASIC_HELP = "Add, edit or delete events."

BASIC_USAGES = [
        "@event object name [= event name]",
        "@event/add object name = event name [parameters]",
        "@event/edit object name = event name [event number]",
        "@event/del object name = event name [event number]",
]

BASIC_SWITCHES = [
    "add - add and edit a new event",
    "edit - edit an existing event",
    "del - delete an existing event",
]

VALIDATOR_USAGES = [
        "@event/accept [object name = event name [event number]]",
]

VALIDATOR_SWITCHES = [
    "accept - show events to be validated or accept one",
]

BASIC_TEXT = """
This command is used to manipulate events.  An event can be linked to
an object, to fire at a specific moment.  You can use the command without
switches to see what event are active on an object:
    @event self
You can also specify an event name if you want the list of events associated
with this object of this name:
    @event north = can_traverse
You can also add, edit or remove events using the add, edit or del switches.
"""

VALIDATOR_TEXT = """
You can also use this command to validate events.  Depending on your game
setting, some users might be allowed to add new events, but these events
will not be fired until you accept them.  To see the events needing
validation, enter the /accept switch without argument:
    @event/accept
A table will show you the events that are not validated yet, who created
it and when.  You can then accept a specific event:
    @event here = enter
Or, if more than one events are connected here, specify the number:
    @event here = enter 3
Use the /del switch to remove events that should not be connected.
"""

class CmdEvent(COMMAND_DEFAULT_CLASS):

    """Command to edit events."""

    key = "@event"
    locks = "cmd:perm({})".format(VALIDATING)
    aliases = ["@events", "@ev"]
    if WITH_VALIDATION:
        locks += " or perm({})".format(WITH_VALIDATION)
    help_category = "Building"


    def get_help(self, caller, cmdset):
        """
        Return the help message for this command and this caller.

        The help text of this specific command will vary depending
        on user permission.

        Args:
            caller (Object or Player): the caller asking for help on the command.
            cmdset (CmdSet): the command set (if you need additional commands).

        Returns:
            docstring (str): the help text to provide the caller for this command.

        """
        lock = "perm({}) or perm(events_validating)".format(VALIDATING)
        validator = caller.locks.check_lockstring(caller, lock)
        text = "\n" + BASIC_HELP + "\n\nUsages:\n    "

        # Usages
        text += "\n    ".join(BASIC_USAGES)
        if validator:
            text += "\n    " + "\n    ".join(VALIDATOR_USAGES)

        # Switches
        text += "\n\nSwitches:\n    "
        text += "\n    ".join(BASIC_SWITCHES)
        if validator:
            text += "\n    " + "\n".join(VALIDATOR_SWITCHES)

        # Text
        text += "\n" + BASIC_TEXT
        if validator:
            text += "\n" + VALIDATOR_TEXT

        return text

    def func(self):
        """Command body."""
        caller = self.caller
        lock = "perm({}) or perm(events_validating)".format(VALIDATING)
        validator = caller.locks.check_lockstring(caller, lock)

        # First and foremost, get the event handler and set other variables
        self.handler = get_event_handler()
        self.obj = None
        rhs = self.rhs or ""
        self.event_name, sep, self.parameters = rhs.partition(" ")
        self.event_name = self.event_name.lower()
        self.is_validator = validator
        if self.handler is None:
            caller.msg("The event handler is not running, can't " \
                    "access the event system.")
            return

        # Before the equal sign is always an object name
        if self.args.strip():
            self.obj = caller.search(self.lhs)
            if not self.obj:
                return

        # Switches are mutually exclusive
        switch = self.switches and self.switches[0] or ""
        if switch == "":
            if not self.obj:
                caller.msg("Specify an object's name or #ID.")
                return

            self.list_events()
        elif switch == "add":
            if not self.obj:
                caller.msg("Specify an object's name or #ID.")
                return

            self.add_event()
        elif switch == "edit":
            if not self.obj:
                caller.msg("Specify an object's name or #ID.")
                return

            self.edit_event()
        elif switch == "del":
            if not self.obj:
                caller.msg("Specify an object's name or #ID.")
                return

            self.del_event()
        elif switch == "accept" and validator:
            self.accept_event()
        else:
            caller.msg("Mutually exclusive or invalid switches were " \
                    "used, cannot proceed.")

    def list_events(self):
        """Display the list of events connected to the object."""
        obj = self.obj
        event_name = self.event_name
        events = self.handler.get_events(obj)
        types = self.handler.get_event_types(obj)

        if event_name:
            # Check that the event name can be found in this object
            created = events.get(event_name)
            if created is None:
                self.msg("No event {} has been set on {}.".format(event_name, obj))
                return

            # Create the table
            cols = ["Number", "Author", "Updated"]
            if self.is_validator:
                cols.append("Valid")

            table = EvTable(*cols, width=78)
            now = datetime.now()
            for i, event in enumerate(created):
                author = event.get("author")
                author = author.key if author else "|gUnknown|n"
                updated_on = event.get("updated_on")
                if updated_on is None:
                    updated_on = event.get("created_on")

                if updated_on:
                    updated_on = time_format(
                            (now - updated_on).total_seconds(), 1)
                else:
                    updated_on = "|gUnknown|n"

                row = [str(i + 1), author, updated_on]
                if self.is_validator:
                    row.append("Yes" if event.get("valid") else "no")
                table.add_row(*row)

            table.reformat_column(0, align="r")
            self.msg(table)
        else:
            table = EvTable("Event name", "Number", "Lines", "Description",
                    width=78)
            for name, infos in sorted(types.items()):
                number = len(events.get(name, []))
                lines = sum(len(e["code"].splitlines()) for e in \
                        events.get(name, []))
                description = infos[1].splitlines()[0]
                table.add_row(name, number, lines, description)

            table.reformat_column(1, align="r")
            table.reformat_column(2, align="r")
            self.msg(table)

    def add_event(self):
        """Add an event."""
        obj = self.obj
        event_name = self.event_name
        types = self.handler.get_event_types(obj)

        # Check that the event exists
        if not event_name in types:
            self.msg("The event name {} can't be found in {} of " \
                    "typeclass {}.".format(event_name, obj, type(obj)))
            return

        definition = types[event_name]
        description = definition[1]
        self.msg(description)

        # Open the editor
        event = self.handler.add_event(obj, event_name, "",
                self.caller, False)
        self.caller.db._event = event
        EvEditor(self.caller, loadfunc=_ev_load, savefunc=_ev_save,
                quitfunc=_ev_quit, key="Event {} of {}".format(
                event_name, obj), persistent=True, codefunc=_ev_save)

    def edit_event(self):
        """Edit an event."""
        obj = self.obj
        event_name = self.event_name
        parameters = self.parameters
        events = self.handler.get_events(obj)
        types = self.handler.get_event_types(obj)

        # Check that the event exists
        if not event_name in events:
            self.msg("The event name {} can't be found in {}.".format(
                    event_name, obj))
            return

        # Check that the parameter points to an existing event
        try:
            parameters = int(parameters) - 1
            assert parameters >= 0
            event = events[event_name][parameters]
        except (AssertionError, ValueError):
            self.msg("The event {} {} cannot be found in {}.".format(
                    event_name, parameters, obj))
            return

        definition = types[event_name]
        description = definition[1]
        self.msg(description)

        # Open the editor
        event = dict(event)
        event["obj"] = obj
        event["name"] = event_name
        event["number"] = parameters
        self.caller.db._event = event
        EvEditor(self.caller, loadfunc=_ev_load, savefunc=_ev_save,
                quitfunc=_ev_quit, key="Event {} of {}".format(
                event_name, obj), persistent=True, codefunc=_ev_save)

    def del_event(self):
        """Delete an event."""
        obj = self.obj
        self.msg("Calling del.")

    def accept_event(self):
        """Accept an event."""
        obj = self.obj
        self.msg("Calling accept.")

# Private functions to handle editing
def _ev_load(caller):
    return caller.db._event and caller.db._event.get("code", "") or ""

def _ev_save(caller, buf):
    """Save and add the event."""
    lock = "perm({}) or perm(events_without_validation)".format(
            WITHOUT_VALIDATION)
    autovalid = caller.locks.check_lockstring(caller, lock)
    event = caller.db._event
    handler = get_event_handler()
    if not handler or not event or not all(key in event for key in \
            ("obj", "name", "number", "valid")):
        caller.msg("Couldn't save this event.")
        return False

    handler.edit_event(event["obj"], event["name"], event["number"], buf,
            caller, valid=autovalid)
    return True

def _ev_quit(caller):
    del caller.db._event
    caller.msg("Exited the code editor.")
