# Clover

![Example](ex.png)

Clover is a small project to
1. Automatically collect a selection of open weather data from SMHI
2. Display this data using an SVG map of Sweden

The purpose is a [D3](https://d3js.org/) excercise using some real data. The specifics are described in 
[blog postings](https://www.viltstigen.se/wolfblog/2019/03/30/lets-make-a-map/).
Use [this link](https://www.viltstigen.se/clover/index.html) to view the implementation

A variation of techniques is used, deploying a client-server architecture.
* D3 is used to render the weather data in a Web browser client, javascript code in `index.html`
* Python scripts is used to collect data and dispatch this to the client in JSON format when requested
    * `emitter.py`, a flask based python script, reading the data the collector-script stored and returning this 
    in JSON format.
    * `collector.py`, a threaded daemon script collecting data, configured to run as a systemd timer once per day.
    Install `clover.timer` (see below for `clover.service`):
      
    
    [Unit]
    Description=Clover, collecting weather data once per day
    Requires=clover.service
    
    [Timer]
    # To enable this, systemctl needs to be done in the following order
    #   $ sudo systemctl enable /home/pi/rpi2/etc/systemd/user/clover.timer
    #   $ sudo systemctl start claps.service
    # The first (enable) command will create symlink and enable the service so it get started at reboot
    #
    Unit=clover.service
    OnCalendar=*-*-* 00:01:00
    
    [Install]
    WantedBy=timers.target

    $ systemctl list-timers
    NEXT                          LEFT          LAST                          PASSED       UNIT                         ACTIVATES
    Sat 2021-05-01 10:10:08 CEST  1h 35min left Sat 2021-05-01 02:40:57 CEST  5h 53min ago apt-daily.timer              apt-daily.service
    Sat 2021-05-01 19:55:51 CEST  11h left      Fri 2021-04-30 19:55:51 CEST  12h ago      systemd-tmpfiles-clean.timer systemd-tmpfiles-clean.service
    Sun 2021-05-02 00:00:00 CEST  15h left      Sat 2021-05-01 00:01:07 CEST  8h ago       logrotate.timer              logrotate.service
    Sun 2021-05-02 00:00:00 CEST  15h left      Sat 2021-05-01 00:01:07 CEST  8h ago       man-db.timer                 man-db.service
    Sun 2021-05-02 00:01:00 CEST  15h left      n/a                           n/a          clover.timer                 clover.service
    Sun 2021-05-02 06:12:37 CEST  21h left      Sat 2021-05-01 06:33:42 CEST  2h 0min ago  apt-daily-upgrade.timer      apt-daily-upgrade.service
    
    6 timers listed.
    Pass --all to see loaded but inactive timers, too.
    
A few tools is used to build the infrastructure, such as [Flask](http://flask.pocoo.org/), 
[Gunicorn](https://gunicorn.org/), [Boostrap](https://getbootstrap.com/), [jQuery](https://jquery.com/), 
[requests](http://docs.python-requests.org/en/master/). 
[Nginx](http://nginx.org/en/) is used as HTTP-proxy and server. See below.

## Infrastructure

Using a raspberry environment, the following nodes are used
* `rpi1`: The primary web-server for the domain [`viltstigen.se`](www.viltstigen.se), running nginx as web proxy/server
* `rpi2`: The server running the `collector` daemon and the `emitter` flask/gunicorn server listening on port 8096

The raspberries are protected by [`ufw` firewall](http://manpages.ubuntu.com/manpages/bionic/en/man8/ufw.8.html) 
that needs to be configured.

The client-to-server flow is
* A webclient on internet wants to reach the clover `index.html` page through `rpi1` which passes the request using 
nginx to `rpi2`.
* `rpi2` returns the `index.html` page to the client that execute the javascript included. This triggers an ajax-request
to download the weather data in JSON format. The ajax request is forwarded by `rpi1/nginx` to `rpi2` on port 8096 where
the `emitter` script is listening. The `emitter` script returns the data reading a file created by the `collector` script.

## Installation

Using python3, requests, flask and gunicorn in a virtual environment, on `rpi2`
    
    $ python3 -m venv /home/pi/app/clover/venv
    
Make sure "/home/pi/app/clover" directory is created and populated with all project files
    
    $ cd /home/pi/app/clover
    $ source venv/bin/activate

Now install in this environment

    (venv) $ pip3 install requests
    (venv) $ pip3 install flask
    (venv) $ pip3 install gunicorn

The `emitter.py` script reads from `/var/local/clover_weather.js`, softlink this

    $ sudo ln -s /home/pi/app/clover/data/weather.js /var/local/clover_weather.js
    
## nginx configuration

On `rpi1`, in nginx configuration file (my case: `/etc/nginx/snippets/locations.conf`) add this,

    location /clover {
        try_files $uri $uri/ $uri/index.html $uri.html @clover;
    }
    
    location @clover {
        # proxy_pass http://rpi2.local; Note, a static IP address makes nginx more robust in case rpi1 is not running
        proxy_pass http://192.168.1.51;
        proxy_redirect     off;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Host $server_name;
        proxy_read_timeout 300;
    }
    
    location /clover_data {
    try_files $uri $uri/ $uri/index.html $uri.html @clover_data;
    }

    location @clover_data {
        # proxy_pass http://rpi2.local; Note, a static IP address makes nginx more robust in case rpi1 is not running
        proxy_pass http://192.168.1.51:8096;
        proxy_redirect     off;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Host $server_name;
        proxy_read_timeout 300;
    }

Do

    $ sudo nginx -t
    nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
    nginx: configuration file /etc/nginx/nginx.conf test is successful
    $ sudo service nginx restart

On `rpi2`, open up the firewall by (unless ufw is configured to allow all traffic on subnet 192.168.x.x)

    $ sudo ufw allow from 192.168.1.0/24 to any port 8096
    $ sudo ufw allow from 192.168.1.0/24 to any port 80

(In case of errors, remove byte compiled code for ufw by: `$ sudo rm /usr/lib/python3/dist-packages/ufw/__pycache__/*.pyc`)

Link the clover directory in the nginx-root (`/var/www/html`) at `rpi2` by (assuming clover is installed at
`/home/pi/app)

    $ sudo ln -s /home/pi/app/clover/ /var/www/html/clover

## gunicorn and Flask

Use [systemd](https://wiki.archlinux.org/index.php/systemd) service for emitter:

    [Unit]
    Description=Clover, collecting weather data
    After=network.target
    
    [Service]
    # To enable this, systemctl needs to be done in the following order
    #   $ sudo systemctl enable /home/pi/rpi2/etc/systemd/user/clover.service
    #   $ sudo systemctl start clover.service
    # The first (enable) command will create symlink and enable the service so it get started at reboot
    #
    Type=simple
    WorkingDirectory=/home/pi/app/clover/py
    User=pi
    Group=www-data
    ExecStart=/home/pi/app/clover/venv/bin/gunicorn -b :8096 --reload emitter:app
    Restart=always
    
    [Install]
    WantedBy=multi-user.target

Check status

    $ systemctl status clover
    ● clover.service - Clover, collecting weather data
       Loaded: loaded (/home/pi/rpi2/etc/systemd/user/clover.service; enabled; vendor preset: enabled)
       Active: active (running) since Sat 2021-05-01 08:06:02 CEST; 9s ago
     Main PID: 7705 (gunicorn)
        Tasks: 3 (limit: 1938)
       CGroup: /system.slice/clover.service
               ├─7705 /home/pi/app/clover/venv/bin/python3 /home/pi/app/clover/venv/bin/gunicorn -b :8096 --reload emitter:app
               └─7708 /home/pi/app/clover/venv/bin/python3 /home/pi/app/clover/venv/bin/gunicorn -b :8096 --reload emitter:app
    
    May 01 08:06:02 rpi2 systemd[1]: Started Clover, collecting weather data.
    May 01 08:06:03 rpi2 gunicorn[7705]: [2021-05-01 08:06:03 +0200] [7705] [INFO] Starting gunicorn 20.1.0
    May 01 08:06:03 rpi2 gunicorn[7705]: [2021-05-01 08:06:03 +0200] [7705] [INFO] Listening at: http://0.0.0.0:8096 (7705)
    May 01 08:06:03 rpi2 gunicorn[7705]: [2021-05-01 08:06:03 +0200] [7705] [INFO] Using worker: sync
    May 01 08:06:03 rpi2 gunicorn[7705]: [2021-05-01 08:06:03 +0200] [7708] [INFO] Booting worker with pid: 7708

gunicorn is now running a WSGIserver, listening on port 8096, connected to this is the Flask application that reads
the weather json file, dump the content to a string which is returned from Flask to gunicorn which then respond to the
HTML GET-request submitted upstream by nginx running on `rpi1`.

If needed, debug Flask using

    $ export FLASK_APP=emitter.py
    $ export FLASK_DEBUG=1
    $ flask run --host=0.0.0.0 --port=8096
    
Then try `http://rpi2.local:8096/clover_data` in a browser
