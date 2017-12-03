CraftBeerPi Bot
================

A telegram bot that lets you read infromation from your `CraftBeerPi : The Raspberry PI base Home Brewing Software <https://github.com/Manuel83/craftbeerpi>`_


How to use it?
--------------

Tester:
The following commands are available:
* /status Check temps status
* /timezone Set the timezone (only works if sudo requires no password)
* /time Print time and timezone on device
* /help Get this message

Features
--------

* Lets you set the timezone
* Lets you check the temprature for brewing

Developing
----------

Requirements
~~~~~~~~~~~~

#. Python 3

Install
~~~~~~~

Run the following::

    sudo apt-get install python3-pip
    git clone https://github.com/guysoft/CraftBeerPiBot.git
    cd CraftBeerPiBot
    sudo pip3 install -r requirements.txt
    cd src
    cp config.ini.example config.ini
    
    
Put your bot token ``config.ini``. Then run::

    python3 CraftBeerPiBot/src/craftbeerpibot.py

4. Message ``/start`` to your bot to start.
    

Set up service on startup
-------------------------
Run ``src/add_startup_service.sh`` either as the user you want the service to be run as, or ``src/add_startup_service.sh <user to run script>``


Code contributions are loved!
