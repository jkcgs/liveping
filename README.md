# Liveping

A Python application that makes a live graph of the network ping.
The script must be executed as administrator/root to work. If it
is not, the script will ask for administrative. On Windows, the
[win32api](http://sourceforge.net/projects/pywin32/files/pywin32/)
implementation is required for this to work.

Usage: ./liveping [host]

The host by default is 8.8.8.8 (Google public DNS server)
