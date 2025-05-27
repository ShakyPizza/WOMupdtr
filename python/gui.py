import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import configparser
import os
from datetime import datetime
import json
import asyncio
import aiohttp
from utils.rank_utils import load_ranks, save_ranks, next_rank
from utils.log_csv import log_ehb_to_csv
from WOM import discord_client, wom_client, check_for_rank_changes, list_all_members_and_ranks, group_id, group_passcode

class BotGUI:
    # Class-level message queue
    msg_queue = queue.Queue()
    
    def __init__(self, root):
        self.root = root
        self.root.title("WOMupdtr Bot Control Panel")
        self.root.geometry("1200x800")
        
        # Bot state
        self.bot_running = False
        self.bot_thread = None
        
        # Create message queue for thread-safe updates
        self.msg_queue = BotGUI.msg_queue  # Use the class-level queue
        
        # Load config
        config = configparser.ConfigParser()
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
        config.read(config_file)
        self.config = config

        discord_token       = config['discord']['token']
        channel_id          = int(config['discord']['channel_id'])
        group_id            = int(config['wiseoldman']['group_id'])
        group_passcode      = config['wiseoldman']['group_passcode']
        check_interval      = int(config['settings']['check_interval'])
        run_at_startup      = config['settings'].getboolean('run_at_startup', True)
        print_to_csv        = config['settings'].getboolean('print_to_csv', True)
        print_csv_changes   = config['settings'].getboolean('print_csv_changes', True)
        post_to_discord     = config['settings'].getboolean('post_to_discord', True)
        silent              = config['settings'].getboolean('silent', False)
        debug               = config['settings'].getboolean('debug', False)
        
        # Create main container
        self.main_container = ttk.Frame(root, padding="10")
        self.main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_container.columnconfigure(1, weight=1)
        self.main_container.rowconfigure(1, weight=1)
        
        # Create left sidebar
        self.create_sidebar()
        
        # Create main content area
        self.create_main_content()
        
        # Create status bar
        self.create_status_bar()
        
        # Start message checking
        self.check_queue()
        
    def create_sidebar(self):
        sidebar = ttk.Frame(self.main_container, padding="5")
        sidebar.grid(row=0, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Bot Control Section
        control_frame = ttk.LabelFrame(sidebar, text="Bot Control", padding="5")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start Bot", command=self.start_bot)
        self.start_button.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Bot", command=self.stop_bot, state='disabled')
        self.stop_button.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Button(control_frame, text="Refresh Rankings", command=self.refresh_rankings).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Quick Actions Section
        actions_frame = ttk.LabelFrame(sidebar, text="Quick Actions", padding="5")
        actions_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(actions_frame, text="Update Group Data", command=self.update_group).grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)
        ttk.Button(actions_frame, text="Force Rank Check", command=self.force_check).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)
        ttk.Button(actions_frame, text="Edit Config", command=self.edit_config).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Commands Section
        commands_frame = ttk.LabelFrame(sidebar, text="Available Commands", padding="5")
        commands_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Create a canvas with scrollbar for commands
        canvas = tk.Canvas(commands_frame, height=150)
        scrollbar = ttk.Scrollbar(commands_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add command buttons
        commands = [
            ("Lookup Player", self.show_lookup_dialog),
            ("Update Player", self.show_update_dialog),
            ("Check Next Rank", self.show_rankup_dialog),
            ("Link Discord User", self.show_link_dialog),
            ("Subscribe All", self.show_subscribe_all_dialog),
            ("Unsubscribe All", self.show_unsubscribe_all_dialog),
            ("Refresh Group", self.update_group),
            ("Force Check", self.force_check),
            ("Debug Group", self.debug_group)
        ]
        
        for i, (text, command) in enumerate(commands):
            ttk.Button(scrollable_frame, text=text, command=command).grid(row=i, column=0, sticky=(tk.W, tk.E), pady=2)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Settings Section
        settings_frame = ttk.LabelFrame(sidebar, text="Settings", padding="5")
        settings_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Checkbox for auto-refresh
        self.auto_refresh_var = tk.BooleanVar(value=self.config['settings'].getboolean('run_at_startup', True))
        ttk.Checkbutton(settings_frame, text="Auto-refresh on startup", variable=self.auto_refresh_var).grid(row=0, column=0, sticky=(tk.W), pady=2)
        
        # Checkbox for CSV logging
        self.csv_logging_var = tk.BooleanVar(value=self.config['settings'].getboolean('print_to_csv', True))
        ttk.Checkbutton(settings_frame, text="Log to CSV", variable=self.csv_logging_var).grid(row=1, column=0, sticky=(tk.W), pady=2)
        
        # Checkbox for Post to Discord channel
        self.discord_notify_var = tk.BooleanVar(value=self.config['settings'].getboolean('post_to_discord', True))
        ttk.Checkbutton(settings_frame, text="Post to Discord channel", variable=self.discord_notify_var).grid(row=2, column=0, sticky=(tk.W), pady=2)
        
        # Check interval setting
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.grid(row=3, column=0, sticky=(tk.W), pady=2)
        ttk.Label(interval_frame, text="Check Interval (min):").pack(side=tk.LEFT)
        self.check_interval_var = tk.StringVar(value=str(int(self.config['settings']['check_interval']) // 60))
        interval_spinbox = ttk.Spinbox(interval_frame, from_=1, to=1440, width=5, textvariable=self.check_interval_var)
        interval_spinbox.pack(side=tk.LEFT, padx=5)
        
    def create_main_content(self):
        # Create notebook for tabs
        notebook = ttk.Notebook(self.main_container)
        notebook.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Logs tab
        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Logs")
        
        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, height=20)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        # Rankings tab
        rankings_frame = ttk.Frame(notebook)
        notebook.add(rankings_frame, text="Rankings")
        
        # Search frame
        search_frame = ttk.Frame(rankings_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_rankings)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Create treeview for rankings
        # Define columns in the order they will be displayed
        self.rankings_tree = ttk.Treeview(
            rankings_frame,
            columns=("rs_username", "Rank", "EHB", "Next Rank"),
            show="headings",
        )
        self.rankings_tree.heading("rs_username", text="RuneScape Username")
        self.rankings_tree.heading("Rank", text="Rank")
        self.rankings_tree.heading("EHB", text="EHB")
        self.rankings_tree.heading("Next Rank", text="Next Rank")
        self.rankings_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(rankings_frame, orient=tk.VERTICAL, command=self.rankings_tree.yview)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.rankings_tree.configure(yscrollcommand=scrollbar.set)
        
        rankings_frame.columnconfigure(0, weight=1)
        rankings_frame.rowconfigure(1, weight=1)
        
        # Fans Management tab
        fans_frame = ttk.Frame(notebook)
        notebook.add(fans_frame, text="Fans")
        
        # Fans management interface
        fans_left = ttk.Frame(fans_frame)
        fans_left.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        ttk.Label(fans_left, text="Link Discord User").grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(fans_left, text="RuneScape Username:").grid(row=1, column=0, sticky=tk.W)
        self.rs_username = ttk.Entry(fans_left)
        self.rs_username.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(fans_left, text="Discord Username:").grid(row=2, column=0, sticky=tk.W)
        self.discord_username = ttk.Entry(fans_left)
        self.discord_username.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Button(fans_left, text="Link User", command=self.link_user).grid(row=3, column=0, columnspan=2, pady=5)
        
        # Fans list
        fans_right = ttk.Frame(fans_frame)
        fans_right.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        ttk.Label(fans_right, text="Current Fans").grid(row=0, column=0, pady=5)
        
        self.fans_tree = ttk.Treeview(fans_right, columns=("fans"), show="headings")
        self.fans_tree.heading("fans", text="Discord Users")
        self.fans_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        fans_frame.columnconfigure(1, weight=1)
        fans_frame.rowconfigure(0, weight=1)
        fans_right.columnconfigure(0, weight=1)
        fans_right.rowconfigure(1, weight=1)
        
        # Refresh displays
        self.refresh_rankings_display()
        self.refresh_fans_display()

        #Create CSV viewer tab
        csv_frame = ttk.Frame(notebook)
        notebook.add(csv_frame, text="CSV Viewer")
        self.csv_text = scrolledtext.ScrolledText(csv_frame, wrap=tk.WORD, height=20)
        self.csv_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        csv_frame.columnconfigure(0, weight=1)
        csv_frame.rowconfigure(0, weight=1)
        # Load CSV data
        try:
            # Locate ehb_log.csv one level above the current file's directory
            csv_file = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ehb_log.csv'))
            if os.path.exists(csv_file):
                with open(csv_file, 'r') as f:
                    csv_data = f.read()
                    self.csv_text.insert(tk.END, csv_data)
            else:
                self.csv_text.insert(tk.END, "No CSV data found.")
        finally:
            # Ensure the CSV text widget is read-only
            self.csv_text.config(state=tk.DISABLED)
            # Configure the main container to expand
            self.main_container.columnconfigure(1, weight=1)
            self.main_container.rowconfigure(1, weight=1)


    def create_status_bar(self):
        status_frame = ttk.Frame(self.main_container)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Status:")
        self.status_label.grid(row=0, column=0, sticky=(tk.W))
        
        # Add bot status indicator
        self.bot_status = ttk.Label(status_frame, text="Bot Stopped", foreground="red")
        self.bot_status.grid(row=0, column=1, sticky=(tk.E))
        
    def log_message(self, message):
        """Log a message to both the GUI and the message queue."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"{timestamp} - {message}"
        self.msg_queue.put(formatted_message)
        
    def check_queue(self):
        """Check for new messages in the queue and update the GUI."""
        try:
            # Process all available messages
            while True:
                try:
                    message = self.msg_queue.get_nowait()
                    self.log_text.insert(tk.END, f"{message}\n")
                    self.log_text.see(tk.END)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error processing queue: {e}")
        finally:
            # Schedule the next check
            self.root.after(100, self.check_queue)
            
    def start_bot(self):
        if not self.bot_running:
            self.log_message("Starting bot...")
            self.bot_running = True
            self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
            self.bot_thread.start()
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.bot_status.config(text="Bot Running", foreground="green")
            
    def stop_bot(self):
        if self.bot_running:
            self.log_message("Stopping bot...")
            self.bot_running = False
            
            # Stop the bot thread if it's running
            if self.bot_thread and self.bot_thread.is_alive():
                try:
                    # Don't try to join if we're in the same thread
                    if threading.current_thread() != self.bot_thread:
                        self.bot_thread.join(timeout=1.0)
                except RuntimeError:
                    pass
            
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.bot_status.config(text="Bot: Stopped", foreground="red")
            
    def refresh_rankings(self):
        self.log_message("Refreshing rankings...")
        try:
            # Create a new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Initialize the client session
                async def init_and_refresh():
                    try:
                        async with asyncio.timeout(30):  # 30 second timeout
                            await list_all_members_and_ranks()
                    except asyncio.TimeoutError:
                        self.log_message("Operation timed out after 30 seconds")
                        raise
                
                # Run the async operation in the new event loop
                loop.run_until_complete(init_and_refresh())
                self.refresh_rankings_display()
                self.log_message("Rankings refreshed successfully!")
            finally:
                try:
                    # Clean up any pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.close()
                except Exception as cleanup_error:
                    self.log_message(f"Error during cleanup: {cleanup_error}")
        except Exception as e:
            self.log_message(f"Error refreshing rankings: {e}")
        
    async def async_update_group(self):
        async with aiohttp.ClientSession() as session:
            url = f"https://api.wiseoldman.net/v2/groups/{group_id}/update-all"
            headers = {"Content-Type": "application/json"}
            payload = {"verificationCode": group_passcode}
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    updated_count = data.get("count", 0)
                    self.log_message(f"Successfully updated {updated_count} members!")
                else:
                    self.log_message(f"Failed to update group: {await response.text()}")
                    
    def update_group(self):
        self.log_message("Updating group data...")
        try:
            asyncio.run(self.async_update_group())
        except Exception as e:
            self.log_message(f"Error updating group: {e}")
        
    def force_check(self):
        self.log_message("Forcing rank check...")
        try:
            # Create a new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Initialize the client session and run check
                async def init_and_check():
                    try:
                        async with asyncio.timeout(30):  # 30 second timeout
                            await check_for_rank_changes()
                    except asyncio.TimeoutError:
                        self.log_message("Operation timed out after 30 seconds")
                        raise
                
                # Run the check_for_rank_changes in the new event loop
                loop.run_until_complete(init_and_check())
                
                self.log_message("Rank check completed!")
                self.refresh_rankings_display()  # Refresh the display after check
            finally:
                try:
                    # Clean up any pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.close()
                except Exception as e:
                    self.log_message(f"Error during cleanup: {e}")
        except Exception as e:
            self.log_message(f"Error during rank check: {e}")
        
    def refresh_rankings_display(self):
        # Clear existing items
        for item in self.rankings_tree.get_children():
            self.rankings_tree.delete(item)
            
        # Load and display rankings
        ranks_data = load_ranks()
        for username, data in sorted(
            ranks_data.items(), key=lambda x: x[1]["last_ehb"], reverse=True
        ):
            next_rank_info = next_rank(username)
            self.rankings_tree.insert(
                "",
                tk.END,
                text=username,
                values=(
                    username,
                    data["rank"],
                    f"{data['last_ehb']:.2f}",
                    next_rank_info,
                ),
            )
            
    def filter_rankings(self, *args):
        search_term = self.search_var.get().lower()
        if not search_term:
            self.refresh_rankings_display()
        else:
            for item in self.rankings_tree.get_children():
                username = self.rankings_tree.item(item)["text"].lower()
                if search_term in username:
                    self.rankings_tree.reattach(item, "", "end")
                else:
                    self.rankings_tree.detach(item)
                
    def refresh_fans_display(self):
        # Clear existing items
        for item in self.fans_tree.get_children():
            self.fans_tree.delete(item)
            
        # Load and display fans
        ranks_data = load_ranks()
        for username, data in ranks_data.items():
            if "discord_name" in data and data["discord_name"]:
                fans = ", ".join(data["discord_name"])
                self.fans_tree.insert("", tk.END, text=username, values=(fans,))
                
    def link_user(self):
        rs_username = self.rs_username.get()
        discord_username = self.discord_username.get()
        
        if not rs_username or not discord_username:
            messagebox.showerror("Error", "Please enter both usernames")
            return
            
        try:
            ranks_data = load_ranks()
            if rs_username in ranks_data:
                if "discord_name" not in ranks_data[rs_username]:
                    ranks_data[rs_username]["discord_name"] = []
                if discord_username not in ranks_data[rs_username]["discord_name"]:
                    ranks_data[rs_username]["discord_name"].append(discord_username)
                    save_ranks(ranks_data)
                    self.refresh_fans_display()
                    self.log_message(f"Linked {discord_username} to {rs_username}")
                    self.rs_username.delete(0, tk.END)
                    self.discord_username.delete(0, tk.END)
                else:
                    messagebox.showinfo("Info", f"{discord_username} is already linked to {rs_username}")
            else:
                messagebox.showerror("Error", f"RuneScape username '{rs_username}' not found")
        except Exception as e:
            messagebox.showerror("Error", f"Error linking user: {e}")
            
    def edit_config(self):
        config_window = tk.Toplevel(self.root)
        config_window.title("Edit Configuration")
        config_window.geometry("600x400")
        
        # Create notebook for different config sections
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Discord settings
        discord_frame = ttk.Frame(notebook)
        notebook.add(discord_frame, text="Discord")
        
        ttk.Label(discord_frame, text="Bot Token:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        token_entry = ttk.Entry(discord_frame, width=50)
        token_entry.insert(0, self.config['discord']['token'])
        token_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(discord_frame, text="Channel ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        channel_entry = ttk.Entry(discord_frame, width=50)
        channel_entry.insert(0, self.config['discord']['channel_id'])
        channel_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # WiseOldMan settings
        wom_frame = ttk.Frame(notebook)
        notebook.add(wom_frame, text="WiseOldMan")
        
        ttk.Label(wom_frame, text="Group ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        group_id_entry = ttk.Entry(wom_frame, width=50)
        group_id_entry.insert(0, self.config['wiseoldman']['group_id'])
        group_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(wom_frame, text="Group Passcode:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        passcode_entry = ttk.Entry(wom_frame, width=50)
        passcode_entry.insert(0, self.config['wiseoldman']['group_passcode'])
        passcode_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Bot settings
        bot_frame = ttk.Frame(notebook)
        notebook.add(bot_frame, text="Bot Settings")
        
        ttk.Label(bot_frame, text="Check Interval (minutes):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        check_interval_entry = ttk.Entry(bot_frame, width=50)
        check_interval_entry.insert(0, str(int(self.config['settings']['check_interval']) // 60))
        check_interval_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Save button
        def save_config():
            try:
                self.config['discord']['token'] = token_entry.get()
                self.config['discord']['channel_id'] = channel_entry.get()
                self.config['wiseoldman']['group_id'] = group_id_entry.get()
                self.config['wiseoldman']['group_passcode'] = passcode_entry.get()
                self.config['settings']['check_interval'] = str(int(check_interval_entry.get()) * 60)
                
                with open('config.ini', 'w') as f:
                    self.config.write(f)
                    
                messagebox.showinfo("Success", "Configuration saved successfully!")
                config_window.destroy()
                self.log_message("Configuration updated")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving configuration: {e}")
                
        ttk.Button(config_window, text="Save", command=save_config).pack(pady=10)
        
    def run_bot(self):
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create a task for the bot
            bot_task = loop.create_task(discord_client.start(self.config['discord']['token']))
            
            # Run the event loop until the bot task is complete
            loop.run_until_complete(bot_task)
            
            # Keep the event loop running
            loop.run_forever()
        except Exception as e:
            self.log_message(f"Error running bot: {e}")
            self.bot_running = False
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.bot_status.config(text="Bot: Stopped", foreground="red")
        finally:
            try:
                # Cancel any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Run until all tasks are cancelled
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
                # Close the client session
                if hasattr(wom_client, '_session') and wom_client._session:
                    loop.run_until_complete(wom_client._session.close())
                
                # Close the event loop
                loop.close()
            except Exception as e:
                self.log_message(f"Error during cleanup: {e}")
            
    def show_lookup_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Lookup Player")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        username_entry = ttk.Entry(dialog)
        username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        def lookup():
            username = username_entry.get()
            if username:
                self.log_message(f"Looking up player: {username}")
                # Add lookup logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Lookup", command=lookup).grid(row=1, column=0, columnspan=2, pady=10)
        
    def show_update_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Player")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        username_entry = ttk.Entry(dialog)
        username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        def update():
            username = username_entry.get()
            if username:
                self.log_message(f"Updating player: {username}")
                # Add update logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Update", command=update).grid(row=1, column=0, columnspan=2, pady=10)
        
    def show_rankup_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Check Next Rank")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        username_entry = ttk.Entry(dialog)
        username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        def check_rank():
            username = username_entry.get()
            if username:
                self.log_message(f"Checking next rank for: {username}")
                # Add rank check logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Check", command=check_rank).grid(row=1, column=0, columnspan=2, pady=10)
        
    def show_link_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Link Discord User")
        dialog.geometry("300x150")
        
        ttk.Label(dialog, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        username_entry = ttk.Entry(dialog)
        username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="Discord Name:").grid(row=1, column=0, padx=5, pady=5)
        discord_entry = ttk.Entry(dialog)
        discord_entry.grid(row=1, column=1, padx=5, pady=5)
        
        def link():
            username = username_entry.get()
            discord_name = discord_entry.get()
            if username and discord_name:
                self.log_message(f"Linking {discord_name} to {username}")
                # Add link logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Link", command=link).grid(row=2, column=0, columnspan=2, pady=10)
        
    def show_subscribe_all_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Subscribe All")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Discord Name:").grid(row=0, column=0, padx=5, pady=5)
        discord_entry = ttk.Entry(dialog)
        discord_entry.grid(row=0, column=1, padx=5, pady=5)
        
        def subscribe():
            discord_name = discord_entry.get()
            if discord_name:
                self.log_message(f"Subscribing {discord_name} to all players")
                # Add subscribe logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Subscribe", command=subscribe).grid(row=1, column=0, columnspan=2, pady=10)
        
    def show_unsubscribe_all_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Unsubscribe All")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Discord Name:").grid(row=0, column=0, padx=5, pady=5)
        discord_entry = ttk.Entry(dialog)
        discord_entry.grid(row=0, column=1, padx=5, pady=5)
        
        def unsubscribe():
            discord_name = discord_entry.get()
            if discord_name:
                self.log_message(f"Unsubscribing {discord_name} from all players")
                # Add unsubscribe logic here
                dialog.destroy()
        
        ttk.Button(dialog, text="Unsubscribe", command=unsubscribe).grid(row=1, column=0, columnspan=2, pady=10)
        
    def debug_group(self):
        self.log_message("Debugging group data...")
        # Add debug logic here

def main():
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
