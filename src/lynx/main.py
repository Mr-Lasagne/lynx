"""An app to facilitate the clerical review of linked data."""

import configparser
import getpass
import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk

import numpy as np
import pandas as pd


class IntroWindow(tk.Tk):
    """A window that prompts the user to choose a CSV file."""

    def __init__(self) -> None:
        """Initialise the intro window."""
        super().__init__()

        # Set the window title.
        self.title("lynx")

        # Initialise the intro window content container.
        self.intro_container = ttk.Frame(self)
        self.intro_container.pack(padx=10)

        # Create some widgets and pack them on the GUI.
        self.intro_text = ttk.Label(
            self.intro_container,
            text=(
                "Welcome to the Clerical Matching Application. \n"
                'Please click "Choose File" to select your file \n'
                "and begin matching."
            ),
            font=("Helvetica", 10),
        )
        self.intro_text.pack(pady=(10, 5))

        # Create the file choice button.
        self.choose_csv_button = ttk.Button(
            self.intro_container, text="Choose CSV", command=self.choose_csv
        )
        self.choose_csv_button.pack(pady=(5, 10))

    def choose_csv(self) -> None:
        """Open a file select window and close the intro window."""
        self.csv_file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        self.destroy()


class ClericalApp(tk.Tk):
    """A window that allows users to clerically review records."""

    def __init__(self, working_file, filename_done, filename_old, config):
        """Initialise the main clerical app window."""
        super().__init__()

        # Initialise the file name variables.
        self.filename_done = filename_done
        self.filename_old = filename_old

        # Set the window title.
        self.title("Clerical Matching")

        # Set the window size to 90% of screen width and 50% of screen
        # height.
        width = int(self.winfo_screenwidth() * 0.9)
        height = int(self.winfo_screenheight() * 0.5)
        self.geometry(f"{width}x{height}")

        # Configure the grid layout to make sure the record frame can
        # expand to fill the window.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create the tool frame.
        self.tool_frame = ttk.LabelFrame(self, text="Tools:")
        self.tool_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # Create a container to hold the scrollable canvas that will
        # contain the record frame.
        self.record_container = ttk.Labelframe(self, text="Records")
        self.record_container.grid(row=1, column=0, padx=10, sticky="nsew")

        # Create the canvas and scrollbars, and attach the scrollbar
        # functionality to the canvas.
        self.canvas = tk.Canvas(self.record_container)
        self.vertical_scrollbar = ttk.Scrollbar(
            self.record_container, orient="vertical", command=self.canvas.yview
        )
        self.horizontal_scrollbar = ttk.Scrollbar(
            self.record_container, orient="horizontal", command=self.canvas.xview
        )
        self.canvas.configure(
            yscrollcommand=self.vertical_scrollbar.set,
            xscrollcommand=self.horizontal_scrollbar.set,
        )

        # Add the scrollbars and canvas to the window.
        self.vertical_scrollbar.pack(side="right", fill="y")
        self.horizontal_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Create the record frame and place it in the canvas.
        self.record_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.record_frame, anchor="nw")

        self.record_frame.bind("<Configure>", self._on_record_frame_configure)

        # Bind the mousewheel to the scrolling.
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 * int(e.delta / 120), "units"),
        )
        self.canvas.bind_all(
            "<Shift-MouseWheel>",
            lambda e: self.canvas.xview_scroll(-1 * int(e.delta / 120), "units"),
        )

        # Create the button frame.
        self.button_frame = ttk.Frame(self)
        self.button_frame.grid(row=2, column=0, columnspan=1, padx=10, pady=10)

        # Create a list of record IDs that have not been matched yet.
        self.not_matched_yet = []

        # Create a protocol for if the user presses the 'X' button (top
        # right).
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # If a 'Match' column exists in the clerical file.
        if {"Match"}.issubset(working_file.columns):
            # This variable indicates whether the user has returned to
            # this file (1) or not (0).
            self.matching_previously_began = 1

        else:
            # Create a 'Match' column and fill with blanks.
            working_file["Match"] = ""
            self.matching_previously_began = 0

        # Convert all columns apart from 'Match' and 'Comments' (if
        # specified) to string.
        for col_header in working_file.columns:
            if col_header in ("Match", "Comments"):
                pass
            else:
                # Convert to string.
                working_file[col_header] = working_file[col_header].astype(str)
                # Remove nan values.
                for i in range(len(working_file)):
                    if working_file[col_header][i] == "nan":
                        working_file.at[i, col_header] = ""

        working_file.fillna("", inplace=True)

        # A counter of the number of checkpoint saves.
        self.checkpointcounter = 0

        # Create a sequential cluster ID number from the cluster ID
        # variable.
        cluster_var = config["cluster_id_number"]["cluster_id"]
        working_file["cluster_sequential_number"] = pd.factorize(
            working_file[cluster_var]
        )[0]

        # A list of cluster numbers over which to iterate.
        clusters_to_iterate = list(working_file["cluster_sequential_number"].unique())

        # Get the starting cluster id.
        self.cluster_index = self.get_starting_cluster_id()

        # Create a variable to indicate the number of cluster IDs.
        self.num_clusters = len(clusters_to_iterate)

        # Get a list of the indices of the records contained within the
        # current cluster.
        self.display_indexes = working_file.index[
            working_file["cluster_sequential_number"] == self.cluster_index
        ].to_list()

        # Create a variable that indicates the length of the current cluster.
        self.len_current_cluster = len(
            working_file["cluster_sequential_number"] == self.cluster_index
        )

        # Create an empty string to record results.
        self.match_string = ""

        # Create the font size component.
        self.text_size = 10
        self.text_bold_boolean = 0
        self.text_bold = ""

        self.style = ttk.Style()
        self.style.configure(".", font=("Helvetica", f"{self.text_size}"))

        # A Boolean flag for the show/hide differences button.
        self.show_hide_diff = 0

        # A container to hold the names of all their tags.
        self.tags_container = {}

        # A dictionary containing column headers as keys and items of
        # the first row as values.
        self.comparison_values = {}

        # A list of all the columns that need comparing.
        self.columns_to_compare = []

        # Create empty lists of labels.
        self.non_iterated_labels = []
        self.iterated_labels = []

        self.draw_recordframe(config, working_file)
        self.draw_button_frame()
        self.draw_tool_frame()

    def _on_record_frame_configure(self, event: tk.Event) -> None:
        """Ensure the scroll region is as tall as the canvas."""
        x1, y1, x2, y2 = self.canvas.bbox("all")
        canvas_height = self.canvas.winfo_height()
        bottom = max(y2, canvas_height)
        self.canvas.configure(scrollregion=(x1, y1, x2, bottom))

    def get_starting_cluster_id(self):
        """Get the ID of the first unreviewed cluster."""
        for i in working_file.index:
            if working_file.loc[i, "Match"] == "":
                return working_file.loc[i, "cluster_sequential_number"]
            else:
                pass

    def draw_button_frame(self):
        """Create the widgets that go in the button frame."""
        self.match_button = tk.Button(
            self.button_frame,
            text="Match",
            font=f"Helvetica {self.text_size}",
            command=lambda: self.update_index(1),
            bg="DarkSeaGreen1",
        )
        self.match_button.grid(row=0, column=0, columnspan=1, padx=15, pady=10)
        self.non_match_button = tk.Button(
            self.button_frame,
            text="No more matches",
            font=f"Helvetica {self.text_size}",
            command=lambda: self.update_index(0),
            bg="light salmon",
        )
        self.non_match_button.grid(row=0, column=1, columnspan=1, padx=15, pady=10)

        self.back_button = tk.Button(
            self.button_frame,
            text="Back",
            font=f"Helvetica {self.text_size}",
            command=lambda: self.go_back(),
        )
        self.back_button.grid(row=0, column=2, columnspan=1, padx=15, pady=10)

        # Disable the back button if no previous clusters exist.
        if self.cluster_index == 0 and self.current_num_cluster_decisions() == 0:
            self.back_button.config(state=tk.DISABLED)

        # Add in the comment widget based on the configuration option.
        if int(config["custom_settings"]["commentbox"]):
            # Create 'Comments' column if one does not exist.
            if "Comments" not in working_file:
                working_file["Comments"] = ""

            # Get the position info from the match button.
            info_button = self.match_button.grid_info()

            self.comment_label = ttk.Label(
                self.button_frame,
                text="Comment:",
                font=f"Helvetica {self.text_size} bold",
            )
            self.comment_label.grid(
                row=info_button["row"] + 1, column=0, columnspan=1, sticky="e"
            )

            self.comment_entry = ttk.Combobox(self.button_frame)
            self.comment_entry.grid(
                row=info_button["row"] + 1,
                column=1,
                columnspan=3,
                sticky="sew",
                padx=5,
                pady=5,
            )

            if (config["custom_settings"]["comment_values"]) is not None:
                self.comment_entry["values"] = (
                    config["custom_settings"]["comment_values"]
                ).split(",")

    def draw_tool_frame(self):
        """Create the tool widgets and populate the tool frame."""
        # Configure the grid so the record counter can move to the right
        # of the tool frame.
        self.tool_frame.grid_columnconfigure(9, weight=1)

        # Create separators for the tool frame buttons.
        self.separator_tf_1 = ttk.Separator(self.tool_frame, orient="vertical")
        self.separator_tf_1.grid(
            row=0, column=3, rowspan=1, sticky="ns", padx=10, pady=5
        )
        self.separator_tf_2 = ttk.Separator(self.tool_frame, orient="vertical")
        self.separator_tf_2.grid(
            row=0, column=7, rowspan=1, sticky="ns", padx=10, pady=5
        )

        self.highlighter_button = tk.Checkbutton(
            self.tool_frame,
            indicatoron=False,
            selectcolor="white",
            text="show/hide differences",
            font=f"Helvetica {self.text_size}",
            command=lambda: self.show_hide_differences(self.show_hide_diff),
        )
        self.highlighter_button.grid(row=0, column=2, padx=5, pady=5)

        self.text_smaller_button = tk.Button(
            self.tool_frame,
            font=f"Helvetica {self.text_size}",
            text="A-",
            height=1,
            width=3,
            command=lambda: self.change_text_size(0),
        )
        self.text_smaller_button.grid(row=0, column=4, sticky="e", pady=5)

        self.text_bigger_button = tk.Button(
            self.tool_frame,
            font=f"Helvetica {self.text_size}",
            text="A+",
            height=1,
            width=3,
            command=lambda: self.change_text_size(1),
        )
        self.text_bigger_button.grid(row=0, column=5, sticky="w", pady=5, padx=2)

        self.bold_button = tk.Button(
            self.tool_frame,
            text="B",
            font=f"Helvetica {self.text_size} bold",
            height=1,
            width=3,
            command=lambda: self.make_text_bold(config, working_file),
        )
        self.bold_button.grid(row=0, column=6, sticky="w", pady=5)

        self.save_button = tk.Button(
            self.tool_frame,
            text="Save and Close",
            font=f"Helvetica {self.text_size}",
            command=lambda: self.save_and_close(),
        )
        self.save_button.grid(row=0, column=8, sticky="e", padx=5, pady=5)

        # Current cluster counter.
        count_msg = f"Cluster: {self.cluster_index + 1} / {self.num_clusters}"

        # Try to calculate and display remaining number of clusters for
        # review.
        try:
            self.counter_matches = ttk.Label(
                self.tool_frame, text=count_msg, font=f"Helvetica {self.text_size}"
            )
            self.counter_matches.grid(row=0, column=9, padx=10, sticky="e")

        # Except when matching is completed.
        except TypeError:
            tk.messagebox.showinfo(
                title="Matching completed",
                message="Please select a different file to clerically match",
            )

            # Close down the application.
            self.destroy()

    def draw_recordframe(self, config, working_file):
        """Create the record frame widgets and populate the record frame."""
        num_match_cols = 0
        # Create column header labels and place all them on row 1,
        # column n + 1.
        for n, column_title in enumerate(config.options("column_headers_and_order")):
            # Remove spaces from the user input and split them into
            # different components.
            col_header = (
                config["column_headers_and_order"][column_title]
                .replace(" ", "")
                .split(",")
            )

            exec(
                f'self.{column_title} = ttk.Label(self.record_frame,text="{col_header[0]}",\
                                                      font=f"Helvetica {self.text_size} bold")'
            )

            exec(
                f"self.{column_title}.grid(row=1,column=n+1,columnspan=1, sticky = tk.W,\
                                            padx=10, pady=3)"
            )

            # Add the executed self.labels for the column headers to the
            # non_iterated_labels list.
            self.non_iterated_labels.append(column_title)
            num_match_cols += 1

        # Iterate over column info and order.
        for n, columnfile_title in enumerate(
            config.options("columnfile_info_and_order")
        ):
            row_num = 3
            sep_row = 4

            # Create a style for the header separator.
            style = ttk.Style()
            style.configure("grey.TSeparator", background="Wheat4")
            header_separator = ttk.Separator(
                self.record_frame, orient="horizontal", style="grey.TSeparator"
            )
            if self.text_size != 10:
                text_size_multiplier = 1 + ((self.text_size - 10) / 10)

            elif self.text_size == 10:
                text_size_multiplier = 1

            # Grid separator.
            header_separator.grid(
                row=2,
                column=0,
                columnspan=num_match_cols + 1,
                sticky="ns",
                ipadx=80 * (num_match_cols + 1) * text_size_multiplier,
                ipady=1,
            )

            for v, display_i in enumerate(self.display_indexes):
                col_header = (
                    config["columnfile_info_and_order"][columnfile_title]
                    .replace(" ", "")
                    .split(",")
                )

                # Create a text label.
                exec(
                    f'self.{col_header[0]}row{v} = tk.Text(self.record_frame,\
                                                            height=1,relief="flat",bg="gray93")'
                )

                # Enter in the text from the DataFrame.
                exec(
                    f'self.{col_header[0]}row{v}.insert("1.0",working_file["{col_header[0]}"][{display_i}])'
                )

                # Configure Text so that it is a specified width and
                # font, and cannot be interacted with.
                exec(
                    f'self.{col_header[0]}row{v}.config(width=len(working_file["{col_header[0]}"][{display_i}])+10,\
                                                         font=f"Helvetica {self.text_size} {self.text_bold}",\
                                                         state=tk.DISABLED)'
                )

                # Grid the text label to the widget.
                exec(
                    f'self.{col_header[0]}row{v}.grid(row={row_num}, column={n + 1},columnspan=1,\
                                                       padx=10, pady=3,sticky="w")'
                )

                # Create a checkbutton and append it to the list of
                # checkbutton variables.
                exec(f"self.check_{v}= tk.IntVar()")
                exec(
                    f"self.checkbutton{v}=tk.Checkbutton(self.record_frame,\
                                                          variable=self.check_{v})"
                )
                exec(f"self.checkbutton{v}.deselect()")
                exec(f"self.checkbutton{v}.grid(row={row_num}, column=0)")

                exec(
                    f"self.rf_separator{v}=ttk.Separator(self.record_frame, orient='horizontal')"
                )
                exec(
                    f"self.rf_separator{v}.grid(row={sep_row}, column=0,\
                                            columnspan={num_match_cols}+1, sticky='ns',\
                                            ipadx=80*({num_match_cols + 1})*{text_size_multiplier},\
                                            ipady=1)"
                )

                if col_header[0] not in self.columns_to_compare:
                    self.columns_to_compare.append(col_header[0])

                # If the 'Match' column is not populated yet, keep the
                # checkbutton clickable.
                if working_file.loc[display_i, "Match"] == "":
                    exec(f"self.checkbutton{v}.config(state=tk.NORMAL)")

                # Otherwise make it un-clickable.
                else:
                    exec(f"self.checkbutton{v}.config(state=tk.DISABLED)")

                row_num += 2
                sep_row += 2

    def update_gui(self, config, working_file):
        """Update the GUI labels based on the record values.

        This function is called whenever the app is interacted with,
        i.e. when pressing the match/non-match/back buttons.
        """
        # Clear the frames.
        for widget in self.record_frame.winfo_children():
            widget.destroy()

        for widget in self.tool_frame.winfo_children():
            widget.destroy()

        for widget in self.button_frame.winfo_children():
            widget.destroy()

        # Redraw everything in the frames.
        self.draw_recordframe(config, working_file)
        self.draw_button_frame()
        self.draw_tool_frame()

        # Clear the comment box entry.
        if int(config["custom_settings"]["commentbox"]):
            self.comment_entry.delete(0, tk.END)

        # Disable the back button if no previous clusters exist.
        if self.cluster_index == 0 and self.current_num_cluster_decisions() == 0:
            self.back_button.config(state=tk.DISABLED)
        else:
            self.back_button.config(state="normal")

        self.tags_container = {}
        self.comparison_values = {}

        if self.show_hide_diff == 1:
            self.show_hide_differences(0)

    def make_text_bold(self, config, working_file):
        """Toggle bold font."""
        if not self.text_bold_boolean:
            self.text_bold_boolean = 1
            self.text_bold = "bold"

        else:
            self.text_bold_boolean = 0
            self.text_bold = ""

        self.update_gui(config, working_file)

    def get_matches(self):
        """Generate a string based on the matches in a cluster."""
        # Create, as a local variable, the list of matches within the
        # current cluster.
        list_of_matches = []

        # Add the index of any that are selected by the checkbox to the
        # list of matches.
        for v, display_i in enumerate(self.display_indexes):
            status = eval(f"self.check_{v}.get()")
            if status:
                list_of_matches.append(display_i)

        # Create a string that is the record IDs that match; separated
        # by a comma. Assign the string to global variable
        # `self.match_string`.
        for i in list_of_matches:
            temp_string = (
                str(working_file[config["record_id_col"]["record_id"]][i]) + ","
            )
            self.match_string = self.match_string + temp_string

    def current_num_cluster_decisions(self):
        """Calculate how many records in the cluster have been reviewed.

        Returns
        -------
        current_num_cluster_decisions : integer
        """
        # A list containing all record IDs for records marked as matches
        # in current cluster.
        current_cluster_decisions = [
            working_file.loc[i, "Match"] for i in self.display_indexes
        ]

        # Counting records as a match if there is a corresponding value
        # in the 'Match' column.
        current_num_cluster_decisions = len(
            [record for record in current_cluster_decisions if record != ""]
        )

        return current_num_cluster_decisions

    def update_df(self, event):
        """Write the review decision to the DataFrame.

        Parameters
        ----------
        event : int
            1 if the 'match' button is pressed, 0 if the 'no more
            matches' button is pressed.
        """
        # Create a list of checkboxes ticked by the user.
        checkboxes_selected = self.match_string.split(",")

        # If the match button is pressed.
        if event == 1:
            # For each record in the current cluster.
            for i in self.display_indexes:
                # If 1 or 0 records are selected, present user with a
                # warning.
                if len(checkboxes_selected) <= 2:
                    tk.messagebox.showwarning(
                        message="Two or more records must be selected to make a match"
                    )

                    break

                # Otherwise if the 'Match' column is currently empty.
                if working_file.loc[i, "Match"] == "":
                    # If a record is selected by a checkbutton.
                    if (
                        working_file[config["record_id_col"]["record_id"]][i]
                        in self.match_string
                    ):
                        # Append the currently selected records' record
                        # ID to the 'Match' column.
                        working_file.loc[i, "Match"] = self.match_string

                        # Remove matched records in cluster from list of
                        # those not yet matched.
                        try:
                            self.not_matched_yet.remove(i)

                        # For cases where matched records have already
                        # been removed (big clusters).
                        except ValueError:
                            pass

                        # If 'commentbox' is specified in the
                        # configuration file.
                        if int(config["custom_settings"]["commentbox"]):
                            # For each row where a checkbox selected,
                            # append the commentbox contents.
                            working_file.loc[i, "Comments"] = self.comment_entry.get()

                    # Append those not selected by a checkbutton to a
                    # list of those not yet matched.
                    else:
                        self.not_matched_yet.append(i)
                else:
                    pass

            # If there are 1 or 0 records remaining without matching
            # decisions.
            if (len(self.display_indexes) - self.current_num_cluster_decisions()) <= 1:
                # For this remaining record, mark it as a non-match.
                for i in self.not_matched_yet:
                    working_file.loc[i, "Match"] = "No match in cluster"

        # If the non-match button clicked.
        else:
            # Mark each record in the cluster that has a null match
            # decision as a non-match.
            for i in self.display_indexes:
                if working_file.loc[i, "Match"] == "":
                    working_file.loc[i, "Match"] = "No match in cluster"

                    # If the commentbox is specified in the
                    # configuration file.
                    if int(config["custom_settings"]["commentbox"]):
                        working_file.loc[i, "Comments"] = self.comment_entry.get()

    def go_back(self):
        """Go back to the previous cluster."""
        # Get the number of decisions made in the current cluster.
        num_decisions = self.current_num_cluster_decisions()

        # Update `cluster_index` if there are no decisions in current
        # cluster.
        if num_decisions == 0:
            self.cluster_index -= 1
            self.display_indexes = working_file.index[
                working_file["cluster_sequential_number"] == self.cluster_index
            ].to_list()

        # Reset new (previous record) to empty strings.
        for i in self.display_indexes:
            working_file.loc[i, "Match"] = ""
            working_file.loc[i, "Comments"] = ""

        # Clean the match string.
        self.match_string = ""

        # Clear the list of not matched yet.
        self.not_matched_yet.clear()

        # Update the GUI.
        self.update_gui(config, working_file)

        # Set the match and non-match buttons to normal state.
        self.match_button.config(state="normal")
        self.non_match_button.config(state="normal")

        # Handling when the user presses the back button on the first
        # cluster in the data.
        try:
            self.matchdone.destroy()
        except AttributeError:
            pass

    def check_matching_done(self):
        """Check if the review is complete.

        Check if the number of iterations is greater than the number of
        rows and, if so, break the loop.

        Returns
        -------
        Literal[1, 0]
            If 1, stop the GUI - if 0, continue updating the GUI.
        """
        # Query whether the current record matches the total number of
        # records.
        if self.cluster_index > (self.num_clusters - 1):
            # Disable the 'match' and 'non-match' buttons.
            self.match_button.configure(state=tk.DISABLED)
            self.non_match_button.configure(state=tk.DISABLED)
            # Inform the user that matching is finished.
            self.matchdone = ttk.Label(
                self, text="Matching Finished. Press save and close.", foreground="red"
            )
            self.matchdone.grid(row=1, column=0, columnspan=1)

            return 1
        else:
            return 0

    def save_and_close(self):
        """Save the working_file DataFrame and close the GUI."""
        try:
            # Check whether matching has now finished (i.e. they have
            # completed all records).
            if self.cluster_index == (self.num_clusters):
                # If matching is now complete, rename the file.
                os.rename(self.filename_old, self.filename_done)
                working_file.to_csv(self.filename_done, index=False)

            else:
                # If not it yet finished, save it using the old file
                # name.
                working_file.to_csv(self.filename_old, index=False)

            # Close down the app.
            self.destroy()
        except PermissionError:
            tk.messagebox.showwarning(
                message="This clerical sample is already open in another program. Please close that program."
            )

            print(
                "\nThis clerical sample is already open in another program. Please close that program."
            )

    def show_hide_differences(self, toggle):
        """Toggle the highlighting of differences between records.

        Parameters
        ----------
        toggle : int
            A variable to indicate if the show/hide differences is
            already on.
        """
        if toggle == 0:
            # make show show diff variable 1 so that next time this function is
            # called it will remove tags
            self.show_hide_diff = 1

            # For the first row in the cluster: for each column to compare;
            # add col and value to self.comparisso_values
            for col in self.columns_to_compare:
                self.comparison_values[col] = working_file.loc[
                    self.display_indexes[0], col
                ]

                # create a dictionary for the current comparison
                current_comparison = {}

                # for each comparison row
                for n, current_comparison_row in enumerate(self.display_indexes[1:]):
                    # create column:value pair
                    current_comparison[col] = working_file.loc[
                        current_comparison_row, col
                    ]
                    # For the values in datarows that need to be highlighted

                    # some empty variables to control the flow of the difference indicator
                    # a list of list to hold start and end of difference value:
                    char_consistent = []

                    # a list of the start and end value of differences for the current iteration:
                    container = []
                    string_start = 1
                    string_end = 0
                    count = 0

                    # zip comparison values and current comparison and compare each zipped item
                    for char_comparison, char_highlight in zip(
                        self.comparison_values[col], current_comparison[col]
                    ):
                        # if the comparison char is not the same as the highlighter char
                        if char_comparison != char_highlight:
                            # if this is the first diff append count to container
                            if string_start:
                                # start the container values
                                container.append(count)

                                string_start = 0

                            # if we are at the end of string comparison
                            if (
                                count
                                == min(
                                    len(self.comparison_values[col]),
                                    len(current_comparison[col]),
                                )
                                - 1
                            ):
                                container.append(count + 1)
                                # pass this start and end values to the overall container
                                char_consistent.append(container)

                        elif char_comparison == char_highlight:
                            if string_end == string_start:
                                # add it to the container to complete the char number
                                # differences
                                container.append(count)

                                # restart this variable
                                string_start = 1

                                # pass this start and end values to the overall container
                                char_consistent.append(container)

                                container = []
                        # increase the count
                        count += 1

                    # for each tag # in char consistent create the tag and save the tag name
                    for tag_adder in range(len(char_consistent)):
                        if col in self.tags_container:
                            temp_val = f"{col}_diff{str(tag_adder)}"
                            if temp_val not in self.tags_container[col]:
                                self.tags_container[col].append(
                                    f"{col}_diff{str(tag_adder)}"
                                )

                        else:
                            self.tags_container[col] = [f"{col}_diff{str(tag_adder)}"]

                        exec(
                            f'self.{col}row{n + 1}.tag_add(f"{col}_diff{str(tag_adder)}",\
                                                          f"1.{char_consistent[tag_adder][0]}",\
                                                          f"1.{char_consistent[tag_adder][-1]}")'
                        )

                        exec(
                            f'self.{col}row{n + 1}.tag_config(f"{col}_diff{str(tag_adder)}",\
                                                             background="yellow",\
                                                             foreground = "black")'
                        )

        else:
            # reset this variable
            self.show_hide_diff = 1

            # for all variable labels with differences - remove the tag labels
            for n in range(0, len(self.display_indexes) - 1):
                # for columns in self.columns_to_compare:
                for col, value in self.tags_container.items():
                    for item in value:
                        exec(f"self.{col}row{n + 1}.tag_remove('{item}','1.0','end')")

            self.show_hide_diff = 0

    def update_index(self, event):
        """Update the working file index.

        Also direct other functions to update the working file and the
        GUI.

        Parameters
        ----------
        event : int
            This determines where to add a 1 or a 0 to the df.
        """
        # Update the list of matching record IDs.
        self.get_matches()

        # Update the underlying DataFrame with matching record IDs.
        self.update_df(event)

        # Update the GUI labels.
        self.update_gui(config, working_file)

        # Reset the 'match' string so different pairings can be made in
        # that cluster.
        self.match_string = ""

        # Clear the list of records in the cluster remaining unmatched.
        self.not_matched_yet.clear()

        # If the 'match' button has been clicked and there are still
        # unmatched records in cluster.
        if (
            len(self.display_indexes) > self.current_num_cluster_decisions()
            and event == 1
        ):
            pass

        # If no more matches can be made in the cluster or the 'no more
        # matches' button is clicked.
        else:
            # Update the `cluster_index` and display indexes to
            # reference the new cluster.
            self.cluster_index += 1
            self.display_indexes = working_file.index[
                working_file["cluster_sequential_number"] == self.cluster_index
            ].to_list()
            self.len_current_cluster = len(self.display_indexes)

            stp_gui = self.check_matching_done()
            self.tags_container = {}

            # Check if the user has reached the end of the script.
            if stp_gui:
                pass
                # Could add in additional functionality here to do with
                # saving the working_file.
            else:
                # Update the GUI.
                self.update_gui(config, working_file)

    def change_text_size(self, size_change):
        """Adjust the size of the font.

        Parameters
        ----------
        size_change : int
            Will change the font size based on argument passed.
        """
        # Depending on the argument passed - increase/decrease font
        # size/geometry parameters.
        if size_change:
            self.text_size += 1
        else:
            self.text_size -= 1

        # Update the GUI.
        self.update_gui(config, working_file)

    def on_exit(self):
        """Prompt the user to save and exit."""
        # If they click yes.
        if tk.messagebox.askyesno(
            "Exit", "Are you sure you want to exit WITHOUT saving?"
        ):
            # Check if this is the first time they are accessing it.
            if not self.matching_previously_began & self.checkpointcounter == 0:
                # Then rename the file removing their username and
                # 'inProgress' tag
                os.rename(
                    self.filename_old,
                    "_".join(self.filename_old.split("_")[0:-2]) + ".csv",
                )

            self.destroy()


if __name__ == "__main__":
    # Import the configuration file for the project.
    config = configparser.ConfigParser()
    config.read("config.ini")

    # Grab user credentials.
    user = getpass.getuser()

    # Run the Intro GUI.
    intro_window = IntroWindow()
    intro_window.mainloop()

    # Create file path variables, load in the selected data, and specify
    # column variables.
    try:
        # Check if the user running it has matched records in this file
        # before.
        if "inProgress" in intro_window.csv_file.split("/")[-1]:
            # If it is the same user.
            if user in intro_window.csv_file.split("/")[-1]:
                # Do not rename the file.
                renamed_file = intro_window.csv_file

                # Create the file path name for when the file is
                # finished.
                filepath_done = f"{'/'.join(renamed_file.split('/')[:-1])}/{renamed_file.split('/')[-1][0:-15]}_DONE.{renamed_file.split('/')[-1].split('.')[-1]}"

            else:
                # Rename the file to contain the additional user.
                renamed_file = f"{'/'.join(intro_window.csv_file.split('/')[:-1])}/{intro_window.csv_file.split('/')[-1].split('.')[0][0:-11]}_{user}_inProgress.{intro_window.csv_file.split('/')[-1].split('.')[-1]}"
                os.rename(rf"{intro_window.csv_file}", rf"{renamed_file}")

                # Create the filepath name for when the file is
                # finished.
                filepath_done = f"{'/'.join(renamed_file.split('/')[:-1])}/{renamed_file.split('/')[-1][0:-15]}_DONE.{renamed_file.split('/')[-1].split('.')[-1]}"

        # If a user is picking this file again and its done.
        elif "DONE" in intro_window.csv_file.split("/")[-1]:
            # If it is the same user.
            if user in intro_window.csv_file.split("/")[-1]:
                # Do not change file path done - keep it as it is.
                filepath_done = intro_window.csv_file

                # Rename the file.
                renamed_file = f"{'/'.join(intro_window.csv_file.split('/')[:-1])}/{intro_window.csv_file.split('/')[-1][0:-9]}_inProgress.{intro_window.csv_file.split('/')[-1].split('.')[-1]}"
                os.rename(rf"{intro_window.csv_file}", rf"{renamed_file}")
            # If it is a different user.
            else:
                # Rename the file to include the additional user.
                renamed_file = f"{'/'.join(intro_window.csv_file.split('/')[:-1])}/{intro_window.csv_file.split('/')[-1].split('.')[0][0:-5]}_{user}_inProgress.{intro_window.csv_file.split('/')[-1].split('.')[-1]}"
                os.rename(rf"{intro_window.csv_file}", rf"{renamed_file}")

                # Create the filepath done.
                filepath_done = f"{'/'.join(renamed_file.split('/')[:-1])}/{renamed_file.split('/')[-1][0:-15]}_DONE.{renamed_file.split('/')[-1].split('.')[-1]}"
        else:
            # Resave this file with the user ID and '_inProgress' at the
            # end so no one else selects it.
            renamed_file = f"{'/'.join(intro_window.csv_file.split('/')[:-1])}/{intro_window.csv_file.split('/')[-1].split('.')[0]}_{user}_inProgress.{intro_window.csv_file.split('/')[-1].split('.')[-1]}"
            os.rename(rf"{intro_window.csv_file}", rf"{renamed_file}")

            # Create the file path name for when the file is finished.
            filepath_done = f"{'/'.join(renamed_file.split('/')[:-1])}/{renamed_file.split('/')[-1][0:-15]}_DONE.{renamed_file.split('/')[-1].split('.')[-1]}"

    except PermissionError:
        tk.messagebox.showwarning(
            message="This clerical sample is open in another program. Please close this and restart CROW."
        )

    try:
        working_file = pd.read_csv(renamed_file)

    except FileNotFoundError or NameError:
        sys.exit(
            "\n\nThis clerical sample is open in another program. Please close this and restart CROW."
        )

    # Data validation step.
    record_id = config["record_id_col"]["record_id"]

    working_file["duplicated_record"] = np.where(
        working_file[record_id].duplicated(), 1, 0
    )

    duplicates = working_file[working_file["duplicated_record"] == 1][
        record_id
    ].tolist()

    if len(working_file) != len(working_file[record_id].unique()):
        raise ValueError(f"the record ID(s): {duplicates} is not unique!")

    del (record_id, duplicates)

    working_file = working_file.drop(columns="duplicated_record")

    app = ClericalApp(working_file, filepath_done, renamed_file, config)
    app.mainloop()

    print(
        "\n Number of records matched:",
        str(
            len(
                working_file[
                    (working_file.Match != "No match in cluster")
                    & (working_file.Match != "")
                ]
            )
        ),
    )
