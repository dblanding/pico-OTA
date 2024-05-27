import urequests
import os
import json
import machine
from time import sleep

class OTAUpdater:
    """ This class handles OTA updates. It checks for updates (using version number),
        then downloads and installs multiple filenames, separated by commas."""

    def __init__(self, repo_url, *filenames):
        
        if "www.github.com" in repo_url :
            print(f"Updating {repo_url} to raw.githubusercontent")
            self.repo_url = repo_url.replace("www.github","raw.githubusercontent")
        elif "github.com" in repo_url:
            print(f"Updating {repo_url} to raw.githubusercontent'")
            self.repo_url = repo_url.replace("github","raw.githubusercontent")            
        self.version_url = self.repo_url + 'version.json'
        print(f"version url is: {self.version_url}")
        self.filename_list = [filename for filename in filenames]

        # get the current version (stored in version.json)
        if 'version.json' in os.listdir():    
            with open('version.json') as f:
                self.current_version = int(json.load(f)['version'])
            print(f"Current device firmware version is '{self.current_version}'")

        else:
            self.current_version = 0
            # save the current version
            with open('version.json', 'w') as f:
                json.dump({'version': self.current_version}, f)

    def fetch_new_code(self, filename):
        """ Fetch the code from the repo, returns False if not found."""
    
        # Fetch the latest code from the repo.
        self.firmware_url = self.repo_url + filename
        response = urequests.get(self.firmware_url)
        if response.status_code == 200:
            print(f'Fetched file {filename}, status: {response.status_code}')
    
            # Save the fetched code to file (with prepended '_')
            new_code = response.text
            with open(f'_{filename}', 'w') as f:
                f.write(new_code)
            print(f'Saved as _{filename}')
            return True
        
        elif response.status_code == 404:
            print(f'Firmware not found - {self.firmware_url}.')
            return False

    def check_for_updates(self):
        """ Check if updates are available. (Note: GitHub caches values for 5 min.)"""
        
        print(f'Checking for latest version... on {self.version_url}')
        response = urequests.get(self.version_url)
        
        data = json.loads(response.text)
        
        print(f"data is: {data}, url is: {self.version_url}")
        print(f"data version is: {data['version']}")
        # Turn list to dict using dictionary comprehension
        # my_dict = {data[i]: data[i + 1] for i in range(0, len(data), 2)}
        
        self.latest_version = int(data['version'])
        print(f'latest version is: {self.latest_version}')
        
        # compare versions
        newer_version_available = True if self.current_version < self.latest_version else False
        
        print(f'Newer version available: {newer_version_available}')    
        return newer_version_available
    
    def download_and_install_update_if_available(self):
        """ Check for updates, download and install them."""
        if self.check_for_updates():

            # Fetch new code
            for filename in self.filename_list:
                self.fetch_new_code(filename)

            # Overwrite current code with new
            for filename in self.filename_list:
                newfile = f"_{filename}"
                os.rename(newfile, filename)
                print(f'Renamed _{filename} to {filename}, overwriting existing file')

            # save the current version
            with open('version.json', 'w') as f:
                json.dump({'version': self.latest_version}, f)
            print('Update version from {self.current_version} to {self.latest_version}')

            # Restart the device to run the new code.
            print('Restarting device...')
            sleep(0.3)
            machine.reset() 
        else:
            print('No new updates available.')
