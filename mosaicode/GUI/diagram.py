# -*- coding: utf-8 -*-
"""
This module contains the Diagram class.
"""
import gi
import copy
gi.require_version('Gtk', '3.0')
gi.require_version('GooCanvas', '2.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GooCanvas
from block import Block
from connector import Connector
from mosaicode.system import System as System
from mosaicode.model.diagrammodel import DiagramModel
from mosaicode.model.plugin import Plugin
import gettext
_ = gettext.gettext


class Diagram(GooCanvas.Canvas, DiagramModel):
    """
    This class contains the methods related to Diagram class.
    """

    # ----------------------------------------------------------------------

    def __init__(self, main_window):
        GooCanvas.Canvas.__init__(self)
        DiagramModel.__init__(self)
        self.set_property("expand", True)

        self.last_clicked_point = (None, None)
        self.main_window = main_window

        self.curr_connector = None
        self.current_widgets = []

        self.grab_focus()
        self.connect("motion-notify-event", self.__on_motion_notify)
        self.connect_after("button_press_event", self.__on_button_press)
        self.connect_after("button_release_event", self.__on_button_release)
        self.connect_after("key-press-event", self.__on_key_press)

        self.connect("drag_data_received", self.__drag_data_received)
        self.drag_dest_set(
            Gtk.DestDefaults.MOTION |
            Gtk.DestDefaults.HIGHLIGHT |
            Gtk.DestDefaults.DROP,
            [Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags.SAME_APP, 1)],
            Gdk.DragAction.DEFAULT | Gdk.DragAction.COPY)

        self.white_board = None
        self.show_grid = False
        self.select_rect = None
        self.__update_white_board()
        self.scrolled_window = None
        self.set_property("has-tooltip", True)  # Allow tooltip on elements
        self.show()

        # Used for cycle detection
        self.__marks = None

    # ----------------------------------------------------------------------
    def set_scrolled_window(self, frame):
        """
        This method set scrolled window.

            Parameters:
                * **frame**

        """
        self.scrolled_window = frame

    # ----------------------------------------------------------------------
    def __on_motion_notify(self, canvas_item, event):
        scale = self.get_scale()
        # Select elements
        if self.select_rect is not None:
            self.__update_select(event.x / scale, event.y / scale)
            items = self.get_items_in_area(
                self.select_rect.bounds, True, False, True)
            self.current_widgets = []
            for item in items:
                if not isinstance(item, Connector) and not \
                        isinstance(item, Block):
                    continue
                if item not in self.current_widgets:
                    self.current_widgets.append(item)
            self.update_flows()
            return True  # Abort other events

        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            for connector in self.connectors:
                connector.update_flow()

        if self.curr_connector is None:
            return False
        point = (event.x / scale, event.y / scale)
        self.curr_connector.update_tracking(point)
        return False

    # ----------------------------------------------------------------------
    def __on_key_press(self, widget, event=None):
        grid = System.properties.grid
        modifier_mask = Gtk.accelerator_get_default_mod_mask()
        event.state = event.state & modifier_mask
        if event.state == Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Up:
                self.move_selected_blocks(0, -grid*5)
                return True

            if event.keyval == Gdk.KEY_Down:
                self.move_selected_blocks(0, grid*5)
                return True
            if event.keyval == Gdk.KEY_Left:
                self.move_selected_blocks(-grid*5, 0)
                return True
            if event.keyval == Gdk.KEY_Right:
                self.move_selected_blocks(grid*5, 0)
                return True

        if event.keyval == Gdk.KEY_Delete:
            self.delete()
            return True

        if event.keyval == Gdk.KEY_Up:
            self.move_selected_blocks(0, -grid)
            return True
        if event.keyval == Gdk.KEY_Down:
            self.move_selected_blocks(0, grid)
            return True
        if event.keyval == Gdk.KEY_Left:
            self.move_selected_blocks(-grid, 0)
            return True
        if event.keyval == Gdk.KEY_Right:
            self.move_selected_blocks(grid, 0)
            return True

    # ----------------------------------------------------------------------
    def __on_button_release(self, widget, event=None):
        self.__end_select()

    # ----------------------------------------------------------------------
    def __on_button_press(self, widget, event=None):
        Gtk.Widget.grab_focus(self)
        if event.button == 1:
            self.last_clicked_point = (event.x, event.y)
            self.current_widgets = []
            self.__abort_connection()
            self.update_flows()
            self.__start_select()
            return False
        return False

    # ----------------------------------------------------------------------
    def __start_select(self):
        if self.select_rect is None:
            self.select_rect = GooCanvas.CanvasRect(
                parent=self.get_root_item(),
                x=self.last_clicked_point[0],
                y=self.last_clicked_point[1],
                width=0,
                height=0,
                stroke_color="black",
                fill_color=None,
                line_dash=GooCanvas.CanvasLineDash.newv((4.0, 2.0))
            )

    # ----------------------------------------------------------------------
    def __end_select(self):
        if self.select_rect is not None:
            self.select_rect.remove()
            del self.select_rect
            self.select_rect = None

    # ----------------------------------------------------------------------
    def __update_select(self, x, y):
        scale = self.get_scale()
        xi = 0
        xf = 0
        yi = 0
        yf = 0
        if x > self.last_clicked_point[0] / scale:
            xi = self.last_clicked_point[0] / scale
            xf = x
        else:
            xi = x
            xf = self.last_clicked_point[0] / scale
        if y > self.last_clicked_point[1] / scale:
            yi = self.last_clicked_point[1] / scale
            yf = y
        else:
            yi = y
            yf = self.last_clicked_point[1] / scale
        self.select_rect.set_property("x", xi)
        self.select_rect.set_property("width", xf - xi)
        self.select_rect.set_property("y", yi)
        self.select_rect.set_property("height", yf - yi)

    # ----------------------------------------------------------------------
    def __drag_data_received(self, widget, context, x, y, selection,
                             targetType, time):
        block = self.main_window.main_control.get_selected_block()
        if block is not None:
            block.x = x
            block.y = y
            self.main_window.main_control.add_block(block)
        return

    # ----------------------------------------------------------------------
    def update_scrolling(self):
        """
        This method update scrolling.

        """
        x, y, width, height = self.get_min_max()
        if x >= 0 and y >= 0:
            self.update_flows()
            return
        for block_id in self.blocks:
            block = self.blocks[block_id]
            block.move(0 - x, 0 - y)
        self.update_flows()

    # ----------------------------------------------------------------------
    def insert_block(self, block):
        if self.language is not None and self.language != block.language:
            System.log("Block language is different from diagram language.")
            return False
        if self.language is None or self.language == 'None':
            self.language = block.language

        self.last_id = max(int(self.last_id), int(block.id))
        if block.id < 0:
            block.id = self.last_id
        self.blocks[block.id] = block
        self.last_id += 1
        return True

    # ----------------------------------------------------------------------
    def add_block(self, plugin):
        """
        This method add a block in the diagram.

            Parameters:
                * **plugin**
            Returns:
                * **Types** (:class:`boolean<boolean>`)
        """
        new_block = Block(self, copy.deepcopy(plugin))
        if self.insert_block(new_block):
            self.do("Add")
            self.get_root_item().add_child(new_block, -1)
            return True
        else:
            return False

    # ----------------------------------------------------------------------
    def __valid_connector(self, newCon):
        """
        Parameters:

        Returns
             * **Types** (:class:`boolean<boolean>`)
        """
        for oldCon in self.connectors:
            if oldCon.sink == newCon.sink \
                    and oldCon.sink_port == newCon.sink_port\
                    and not System.ports[newCon.conn_type].multiple:
                System.log(_("Connector Already exists"))
                return False
        if (newCon.sink == newCon.source) or self.__cycle_detection(newCon):
            System.log(_("Recursive connection is not allowed"))
            return False
        return True

    # ----------------------------------------------------------------------
    def __cycle_detection(self, newCon):
        self.__marks = {}
        self.__marks[newCon.source] = None
        self.__marks[newCon.sink] = None
        if self.__dfs(newCon.sink):
            return True
        return False

    # Depth-First Search
    # ----------------------------------------------------------------------
    def __dfs(self, sink):
        for connection in self.connectors:
            if (connection.source != sink):
                continue
            adjacent = connection.sink
            if adjacent in self.__marks:
                return True
            self.__marks[adjacent] = None
            if self.__dfs(adjacent):
                return True
        return False

    # ----------------------------------------------------------------------
    def __abort_connection(self):
        if self.curr_connector is None:
            return
        connector_number = self.get_root_item().find_child(self.curr_connector)
        self.get_root_item().remove_child(connector_number)
        del self.curr_connector
        self.curr_connector = None

    # ----------------------------------------------------------------------
    def start_connection(self, block, output):
        """
        This method start a connection.

            Parameters:
                * **block**
                * **output**

        """
        self.__abort_connection()  # abort any possibly running connections
        if output >= len(block.out_ports):
            return 
        conn_type = block.out_ports[output]["type"]
        self.curr_connector = Connector(self, block, output, conn_type)
        self.get_root_item().add_child(self.curr_connector, -1)
        self.update_flows()

    # ----------------------------------------------------------------------
    def end_connection(self, block, block_input):
        """
        This method end a connection.

            Parameters:
                * **block**
                * **block_input**
            Returns:
                * **Types** (:class:`boolean<boolean>`)
        """
        if self.curr_connector is None:
            return False
        self.curr_connector.sink = block
        self.curr_connector.sink_port = block_input
        if not self.__valid_connector(self.curr_connector):
            self.__abort_connection()
            return False

        out_type = self.curr_connector.source.out_ports[int(self.curr_connector.source_port)]["type"]
        in_type = self.curr_connector.sink.in_ports[int(self.curr_connector.sink_port)]["type"]

        if not out_type == in_type:
            System.log(_("Connection Types mismatch"))
            self.__abort_connection()
            return False
        self.connectors.append(self.curr_connector)
        self.curr_connector = None
        self.update_flows()
        return True

    # ----------------------------------------------------------------------
    def __white_board_event(self, widget, event=None):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button == 1:
                self.white_board.grab_focus()
                self.__abort_connection()
        return False

    # ----------------------------------------------------------------------
    def __update_white_board(self):
        width = self.main_window.get_size()[0]
        height = self.main_window.get_size()[1]
        self.white_board = GooCanvas.CanvasRect(
            parent=self.get_root_item(),
            x=0,
            y=0,
            width=width,
            height=height,
            stroke_color="white",
            fill_color="white")

        self.__draw_grid()

        self.white_board.connect("focus-in-event", self.__white_board_event)

    # ----------------------------------------------------------------------
    def __draw_grid(self):
        if self.show_grid:
            width = self.main_window.get_size()[0]
            height = self.main_window.get_size()[1]

            i = 0
            while i < height:
                GooCanvas.CanvasPath(
                        parent=self.get_root_item(),
                        stroke_color="#F9F9F9",
                        data="M 0 " + str(i) + " L "+ str(width) +" "+ str(i) + ""
                        )
                i = i + System.properties.grid
            i = 0
            while i < width:
                GooCanvas.CanvasPath(
                        parent=self.get_root_item(),
                        stroke_color="#F9F9F9",
                        data="M " + str(i) + " 0 L "+ str(i) + " "+ str(height) +""
                        )
                i = i + System.properties.grid

    # ----------------------------------------------------------------------
    def set_show_grid(self, bool):
        if bool is not None:
            self.show_grid = bool

    # ----------------------------------------------------------------------
    def update_flows(self):
        """
        This method update flows.
        """
        self.white_board.set_property("stroke_color", "white")
        for block_id in self.blocks:
            self.blocks[block_id].update_flow()
        for conn in self.connectors:
            conn.update_flow()

    # ----------------------------------------------------------------------
    def set_file_name(self, file_name):
        """
        This method set name of diagram file.

            Parameters:
                * **file_name** (:class:`str<str>`)

        """
        self.file_name = file_name
        self.main_window.work_area.rename_diagram(self)

    # ----------------------------------------------------------------------
    def __apply_zoom(self):
        self.set_scale(self.zoom)
        self.update_scrolling()
        self.set_modified(True)

    # ----------------------------------------------------------------------
    def set_zoom(self, zoom):
        """
        This method set zoom.

            Parameters:
                * **zoom**
        """
        self.zoom = zoom
        self.__apply_zoom()

    # ----------------------------------------------------------------------
    def change_zoom(self, value):
        """
        This method change zoom.

            Parameters:
               * **value** (:class:`float<float>`)
        """
        zoom = self.zoom
        if value == System.ZOOM_ORIGINAL:
            zoom = System.ZOOM_ORIGINAL
        elif value == System.ZOOM_IN:
            zoom = zoom + 0.1
        elif value == System.ZOOM_OUT:
            zoom = zoom - 0.1
        self.zoom = zoom
        self.__apply_zoom()

    # ----------------------------------------------------------------------
    def show_block_property(self, block):
        """
        This method show block property.

            Parameters:
                * **block**(:class: `Block<mosaicode.GUI.block>`)
        """
        self.main_window.main_control.show_block_property(block)

    # ----------------------------------------------------------------------
    def resize(self, data):
        """
        This method resize diagram.

            Parameters:
               * **data**
        """
        self.set_property("x2", self.main_window.get_size()[0])
        self.white_board.set_property(
            "width", self.main_window.get_size()[0])

    # ----------------------------------------------------------------------
    def select_all(self):
        """
        This method select all blocks in diagram.
        """
        self.current_widgets = []
        for block_id in self.blocks:
            self.current_widgets.append(self.blocks[block_id])
        for conn in self.connectors:
            self.current_widgets.append(conn)
        self.update_flows()

    # ----------------------------------------------------------------------
    def move_selected_blocks(self, x, y):
        """
        This method move selected blocks.

            Parameters:
                * **(x,y)** (:class:`float<float>`)

        """
        self.do("Move blocks")
        for block_id in self.blocks:
            if (self.blocks[block_id] in self.current_widgets):
                block_pos_x, block_pos_y = self.blocks[block_id].get_position()
                x, y = self.check_limit(x, y, block_pos_x, block_pos_y)
                self.blocks[block_id].move(x, y)
        self.update_scrolling()

    # ---------------------------------------------------------------------
    def check_limit(self, x, y, block_pos_x, block_pos_y):
        min_x = 0
        min_y = 0
        max_x = self.main_window.get_size()[0] - 150
        max_y = self.main_window.get_size()[1]

        new_x = x + block_pos_x
        new_y = y + block_pos_y

        if new_x < min_x:
            x = min_x - block_pos_x
        elif new_x > max_x:
            x = max_x - block_pos_x

        if new_y < min_y:
            y = min_y - block_pos_y
        elif new_y > max_y:
            y = max_y - block_pos_y

        return x, y

    # ---------------------------------------------------------------------
    def get_selected_blocks_id(self):
        selected_blocks_id = []

        for block_id in self.blocks:
            if self.blocks[block_id] in self.current_widgets:
                selected_blocks_id.append(block_id)

        return selected_blocks_id

    # ---------------------------------------------------------------------
    def delete(self):
        """
        This method delete a block.

        """
        if len(self.current_widgets) < 1:
            return
        self.do("Delete")
        for widget in self.current_widgets:
            widget.delete()
        self.current_widgets = []
        self.update_flows()

    # ---------------------------------------------------------------------
    def paste(self):
        """
        This method paste a block.
        """
        replace = {}
        self.current_widgets = []
        # interact into blocks, add blocks and change their id
        clipboard = self.main_window.main_control.get_clipboard()
        for widget in clipboard:
            if not isinstance(widget, Block):
                continue
            plugin = Plugin(widget)
            plugin.x += 20
            plugin.y += 20
            plugin.id = -1
            if not self.main_window.main_control.add_block(plugin):
                return
            replace[widget.id] = plugin
            self.current_widgets.append(plugin)
        # interact into connections changing block ids
        for widget in clipboard:
            if not isinstance(widget, Connector):
                continue
            # if a connector is copied without blocks
            if widget.source.id not in replace or widget.sink.id \
                    not in replace:
                continue
            print _("continuing...")
            source = replace[widget.source.id]
            source_port = widget.source_port
            sink = replace[widget.sink.id]
            sink_port = widget.sink_port
            self.start_connection(source, source_port)
            self.current_widgets.append(self.curr_connector)
            self.end_connection(sink, sink_port)
        self.update_flows()

    # ---------------------------------------------------------------------
    def copy(self):
        """
        This method copy a block.
        """
        self.main_window.main_control.reset_clipboard()
        for widget in self.current_widgets:
            self.main_window.main_control.get_clipboard().append(widget)

    # ---------------------------------------------------------------------
    def cut(self):
        """
        This method delete a block.
        """
        if len(self.current_widgets) < 1:
            return
        self.do(_("Cut"))
        self.main_window.main_control.reset_clipboard()
        for widget in self.current_widgets:
            self.main_window.main_control.get_clipboard().append(widget)
            widget.delete()

    # ----------------------------------------------------------------------
    def delete_connection(self, connection):
        """
        This method delete a connection.

            Parameters:
                connection
        """
        if connection in self.connectors:
            self.connectors.remove(connection)
        connection.remove()

    # ----------------------------------------------------------------------
    def delete_block(self, block):
        """
        This method delete a block.

            Parameters:
                block
        """
        if block.id not in self.blocks:
            System.log("Block " + str(block.id) + \
                " is not present in this diagram.")
            return
        for idx in reversed(range(len(self.connectors))):
            if self.connectors[idx].source == block \
                    or self.connectors[idx].sink == block:
                self.delete_connection(self.connectors[idx])
        self.blocks[block.id].remove()
        del self.blocks[block.id]
        self.update_flows()

    # ---------------------------------------------------------------------
    def set_modified(self, state):
        """
        This method set a modification.

            Parameters:
                * **state**
        """
        self.modified = state
        self.main_window.work_area.rename_diagram(self)

    # ---------------------------------------------------------------------
    def grab_focus(self):
        """
        This method define focus.

        """
        Gtk.Widget.grab_focus(self)

    # ---------------------------------------------------------------------
    def redraw(self):
        """
        This method redraw a block.
        """
        while self.get_root_item().get_n_children() != 0:
            self.get_root_item().remove_child(0)
        self.__update_white_board()
        for block_id in self.blocks:
            self.get_root_item().add_child(self.blocks[block_id], -1)
            self.blocks[block_id].adjust_position()
        for connector in self.connectors:
            self.get_root_item().add_child(connector, -1)

    # ---------------------------------------------------------------------
    def do(self, new_msg):
        """
        This method do something
            Parameters:
                * **new_msg** (:class:`str<str>`)
        """
        self.set_modified(True)
        action = (copy.copy(self.blocks), copy.copy(self.connectors), new_msg)
        self.undo_stack.append(action)
        System.log(_("Do: " + new_msg))

    # ---------------------------------------------------------------------
    def undo(self):
        """
        This method undo a modification.
        """
        if len(self.undo_stack) < 1:
            return
        self.set_modified(True)
        action = self.undo_stack.pop()
        self.blocks = action[0]
        self.connectors = action[1]
        msg = action[2]
        self.redraw()
        self.redo_stack.append(action)
        if len(self.undo_stack) == 0:
            self.set_modified(False)
        System.log(_("Undo: " + msg))

    # ---------------------------------------------------------------------
    def redo(self):
        """
        This method redo a modification.
        """
        if len(self.redo_stack) < 1:
            return
        self.set_modified(True)
        action = self.redo_stack.pop()
        self.blocks = action[0]
        self.connectors = action[1]
        msg = action[2]
        self.redraw()
        self.undo_stack.append(action)
        System.log(_("Redo: " + msg))

    # ---------------------------------------------------------------------
    def get_min_max(self):
        """
        This method get min and max.
            Returns

        """
        min_x = self.main_window.get_size()[0]
        min_y = self.main_window.get_size()[1]

        max_x = 0
        max_y = 0

        for block_id in self.blocks:
            block = self.blocks[block_id]
            x, y = block.get_position()
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x + block.width > max_x:
                max_x = x + block.width
            if y + block.height > max_y:
                max_y = y + block.height
        return min_x, min_y, max_x - min_x, max_y - min_y

    # ---------------------------------------------------------------------
    def align_top(self):
        blocks_id = self.get_selected_blocks_id()
        top = self.main_window.get_size()[1]

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            if top > y:
                top = y

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            self.blocks[block_id].move(0, top -y)

        self.update_scrolling()

    # ----------------------------------------------------------------------
    def align_bottom(self):
        blocks_id = self.get_selected_blocks_id()
        bottom = 0

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            if bottom < y:
                bottom = y

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            self.blocks[block_id].move(0, bottom -y)

        self.update_scrolling()

    # ----------------------------------------------------------------------
    def align_left(self):
        blocks_id = self.get_selected_blocks_id()
        left = self.main_window.get_size()[0]

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            if left > x:
                left = x

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            self.blocks[block_id].move(left -x, 0)

        self.update_scrolling()

    # ----------------------------------------------------------------------
    def align_right(self):
        blocks_id = self.get_selected_blocks_id()
        right = 0

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            if right < x:
                right = x

        for block_id in blocks_id:
            x, y = self.blocks[block_id].get_position()
            self.blocks[block_id].move(right -x, 0)

        self.update_scrolling()

# ----------------------------------------------------------------------
