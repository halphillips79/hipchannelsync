import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import datetime
import os
import hipchannel
import json

root = tk.Tk()
root.title("HipStamp / ChannelAdvisor Synchronizer")
title_label = tk.Label(root, text="Welcome to the HipStamp / ChannelAdvisor Inventory Sync App!", font=("Helvetica", 16))
title_label.pack(pady=(10, 0))

def load_hipstamp_inventory():
    with open('hipstamp_inventory_backup.json', 'r') as f:
        return json.load(f)

def load_channeladvisor_inventory():
    with open('channeladvisor_inventory_backup.json', 'r') as f:
        return json.load(f)

def compare_inventories(hip_inventory, ca_inventory):
    comparison_data = []
    ca_inventory_items = ca_inventory.get('value', [])
    ca_inventory_dict = {item['Title']: item for item in ca_inventory_items}
    hip_inventory_items = hip_inventory.get('results', [])
    hip_inventory_dict = {item['name']: item for item in hip_inventory_items}
    for hip_item in hip_inventory_items:
        hip_title = hip_item['name']
        hip_quantity = hip_item['quantity']
        ca_item = ca_inventory_dict.get(hip_title)
        if ca_item:
            ca_quantity = ca_item['TotalAvailableQuantity']
            if hip_quantity != ca_quantity:
                comparison_data.append({
                    "HipStamp Title": hip_title,
                    "HipStamp Quantity": hip_quantity,
                    "ChannelAdvisor Title": ca_item['Title'],
                    "ChannelAdvisor Quantity": ca_quantity
                })
            del ca_inventory_dict[hip_title]
        else:
            comparison_data.append({
                "HipStamp Title": hip_title,
                "HipStamp Quantity": hip_quantity,
                "ChannelAdvisor Title": "N/A",
                "ChannelAdvisor Quantity": "N/A"
            })
    for ca_title, ca_item in ca_inventory_dict.items():
        comparison_data.append({
            "HipStamp Title": "N/A",
            "HipStamp Quantity": "N/A",
            "ChannelAdvisor Title": ca_title,
            "ChannelAdvisor Quantity": ca_item['TotalAvailableQuantity']
        })
    return comparison_data

def compare_quantities():
    hipchannel.log_current_hipstamp_inventory()
    access_token = hipchannel.get_access_token()
    hipchannel.log_current_channeladvisor_inventory(access_token)
    hip_inventory = load_hipstamp_inventory()
    ca_inventory = load_channeladvisor_inventory()
    comparison_data = compare_inventories(hip_inventory, ca_inventory)
    compare_window = tk.Toplevel(root)
    compare_window.title("Compare Inventories")
    columns = ("HipStamp Title", "HipStamp Quantity", "ChannelAdvisor Title", "ChannelAdvisor Quantity")
    inventory_table = ttk.Treeview(compare_window, columns=columns, show='headings')
    for col in columns:
        inventory_table.heading(col, text=col)
    for item in comparison_data:
        inventory_table.insert("", tk.END, values=(
            item.get("HipStamp Title", "N/A"),
            item.get("HipStamp Quantity", "N/A"),
            item.get("ChannelAdvisor Title", "N/A"),
            item.get("ChannelAdvisor Quantity", "N/A")
        ))
    inventory_table.pack(expand=tk.YES, fill=tk.BOTH)
    scrollbar = tk.Scrollbar(compare_window, orient="vertical", command=inventory_table.yview)
    inventory_table.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    inventory_table.pack(side="left", expand=tk.YES, fill=tk.BOTH)

def settings():
    settings_window = tk.Toplevel(root)
    settings_window.title("Settings")
    hipstamp_label = tk.Label(settings_window, text="Check for new HipStamp sales since:")
    hipstamp_label.pack()
    hipstamp_text = tk.Text(settings_window, height=1, width=20)
    hipstamp_text.pack()
    with open('lastcheckedhip.txt', 'r') as file:
        hipstamp_text.insert(tk.END, file.read())
    channeladvisor_label = tk.Label(settings_window, text="Check for new ChannelAdvisor sales since:")
    channeladvisor_label.pack()
    channeladvisor_text = tk.Text(settings_window, height=1, width=20)
    channeladvisor_text.pack()
    with open('lastcheckedchannel.txt', 'r') as file:
        channeladvisor_text.insert(tk.END, file.read())
    instructions_label = tk.Label(settings_window, text="By default, the times given above are when the most recent sync occurred. Changing them will affect the next sync.")
    instructions_label.pack()
    def save_settings():
        with open('lastcheckedhip.txt', 'w') as file:
            file.write(hipstamp_text.get("1.0", tk.END).strip())
        with open('lastcheckedchannel.txt', 'w') as file:
            file.write(channeladvisor_text.get("1.0", tk.END).strip())
        settings_window.destroy()
    save_button = tk.Button(settings_window, text="Save", command=save_settings)
    save_button.pack()

def run_script():
    '''Function to execute the main script and update the GUI accordingly.'''
    
    status_label.config(text="Syncing...")
    root.update()
    try:
        hipchannel.main()
        completion_time = datetime.datetime.now().strftime('%H:%M:%S')
        status_label.config(text=f"Sync Completed at {completion_time}")
        root.update()
    except Exception as e:
        status_label.config(text="Error occurred!")
        root.update()
        messagebox.showerror("Error", str(e))

def write_updated_log(contents):
    with open("sync_log.log", 'w') as f:
        f.writelines(contents)

def clear_selected_lines(listbox):
    selected_indices = listbox.curselection()
    global log_contents
    for i in selected_indices[::-1]:
        del log_contents[i]
        listbox.delete(i)
    write_updated_log(log_contents)

def create_clear_button(tab_frame, listbox):
    style = ttk.Style()
    style.configure('ClearButton.TButton', font=('Helvetica', 14))
    clear_btn = ttk.Button(tab_frame, text="Clear Selected Entries", command=lambda: clear_selected_lines(listbox), style='ClearButton.TButton')
    clear_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

def view_log():
    '''Function to display the contents of the log in a separate window.'''
    
    global log_contents

    if not os.path.exists("sync_log.log"):
        messagebox.showerror("Error", "sync_log.log file not found.")
        return
    
    with open("sync_log.log", 'r') as f:
        log_contents = f.readlines()

    log_window = tk.Toplevel(root)
    log_window.title("Log Viewer")
    log_window.geometry("1200x600")

    tab_control = ttk.Notebook(log_window)
    tab_control.pack(expand=1, fill="both")

    tabs = {}
    for tab_name in ["Full Log", "Successfully Decremented", "No Matching Product", "Duplicates", "Other Errors"]:
        tab_frame = ttk.Frame(tab_control)
        button_frame = ttk.Frame(tab_frame)
        create_clear_button(button_frame, None)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)
        listbox_frame = ttk.Frame(tab_frame)
        tabs[tab_name] = tk.Listbox(listbox_frame, height=30)
        tabs[tab_name].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=tabs[tab_name].yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scrollbar = tk.Scrollbar(tab_frame, orient="horizontal", command=tabs[tab_name].xview)
        h_scrollbar.pack(side=tk.TOP, fill=tk.X)
        tabs[tab_name].configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        create_clear_button(tab_frame, tabs[tab_name])
        tab_control.add(tab_frame, text=tab_name)

    phrases = {
        "Successfully Decremented": "Decremented by",
        "No Matching Product": "No matching product found in",
        "Duplicates": "Multiple matching products found in"
    }
    for line in log_contents:
        if "[DISPLAY]" in line:
            tabs["Full Log"].insert(tk.END, line)
            for tab_name, phrase in phrases.items():
                if phrase in line:
                    tabs[tab_name].insert(tk.END, line)

    error_lines = [line for line in log_contents if "[DISPLAY]" in line and all(phrase not in line for phrase in phrases.values())]
    for line in error_lines:
        tabs["Other Errors"].insert(tk.END, line)

    for tab_name, listbox in tabs.items():
        tab_frame = tab_control.tab(tab_name)['window']

run_button = tk.Button(root, text="Run", command=run_script, font=("Helvetica", 14))
run_button.pack(pady=20)
run_text_label = tk.Label(root, text="This will check both HipStamp and ChannelAdvisor for new sales since the last sync. When it finds one, it will decrement the sale quantity of the corresponding product on the other platform.", font=("Helvetica", 13))
run_text_label.pack(pady=(0, 20))

view_log_button = tk.Button(root, text="View Log", command=view_log, font=("Helvetica", 14))
view_log_button.pack(pady=20)
view_log_text_label = tk.Label(root, text="See which products got updated and which products couldn't get updated.", font=("Helvetica", 13))
view_log_text_label.pack(pady=(0, 20))

compare_button = tk.Button(root, text="Compare Quantities", command=compare_quantities, font=("Helvetica", 14))
compare_button.pack(pady=20)
compare_text_label = tk.Label(root, text="This will display all products whose quantities differ between HipStamp and ChannelAdvisor.", font=("Helvetica", 13))
compare_text_label.pack(pady=(0, 20))

settings_button = tk.Button(root, text="Settings", command=settings, font=("Helvetica", 14))
settings_button.pack(pady=20)
settings_text_label = tk.Label(root, text="Configure settings.", font=("Helvetica", 13))
settings_text_label.pack(pady=(0, 20))

status_label = tk.Label(root, text="")
status_label.pack(pady=20)

root.mainloop()