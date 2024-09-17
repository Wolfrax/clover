#!/usr/bin/python

__author__ = 'mm'

# Mats Melander 2019-03-04
#

import sys
import json as json
import shutil
import requests
import logging
from logging.handlers import RotatingFileHandler
import threading
import os
import datetime

smhi_keys = {
    'temp': '1',            # air temp, momentary value, 1/hour
#    'wind_dir': '3',        # wind direction, average value 10 min, 1/hour
#    'wind_speed': '4',      # wind speed, average value 10 min, 1/hour
#    'rain': '5',            # rain, sum 1/day, at 06:00
#    'pressure': '9',        # air pressure, at sea level, momentary value, 1/hour
}


class smhi_reader(threading.Thread):
    def __init__(self, key):
        threading.Thread.__init__(self)
        self.key = key
        self.smhi = smhi()
        self.result = []
        self.start()

    def run(self):
        self.result = self.smhi.get(self.key)

    def get_data(self):
        return self.result


class smhi:
    def __init__(self):
        self.url = "https://opendata-download-metobs.smhi.se/api.json"  # Root for SMHI REST API

        try:
            api = requests.get(self.url, timeout=10).json()

            # The "next("... construct is used several times below to keep the code short
            # It is equivalent to:
            # for (index, d) in enumerate(lst["version"]):
            #    if d["key"] == "latest":
            #        i = index

            # ind1 points to the latest version of SMHI api, ind2 to the json-type of the latset api
            ind1 = next(i for (i, d) in enumerate(api["version"]) if d["key"] == "latest")
            ind2 = next(i for (i, d) in enumerate(api["version"][ind1]["link"]) if d["type"] == "application/json")
            self.resources = requests.get(api["version"][ind1]["link"][ind2]["href"]).json()
        except (requests.exceptions.RequestException, requests.exceptions.ConnectTimeout) as e:
            logger.error(e)
            sys.exit(0)

    def get(self, key):
        logger.info("Starting {}".format(key))

        # Try to get the indicated resource from the SMHI latest api (setup at initialization)
        # We only handle a pre-defined subset of parameters
        ind1 = next(i for (i, d) in enumerate(self.resources["resource"]) if d["key"] == smhi_keys[key])
        ind2 = next(i for (i, d) in enumerate(self.resources["resource"][ind1]["link"]) if d["type"] == "application/json")

        try:
            stations = requests.get(self.resources["resource"][ind1]["link"][ind2]["href"], timeout=10).json()
        except (requests.exceptions.RequestException,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout) as e:
            logger.error(e)
            return None

        lst = []
        for i, stn in enumerate(stations["station"]):
            logger.debug(f"{stn['name']}")

            if stn["name"] == "SMHI TEST 1":
                # Skip test station by SMHI
                continue

            elem = {}
            ind1 = next(i for (i, d) in enumerate(stn["link"]) if d["type"] == "application/json")

            try:
                lnk = requests.get(stn["link"][ind1]["href"], timeout=10).json()
                ind2 = next((i for (i, d) in enumerate(lnk["period"]) if d["key"] == "latest-day"), None)
                if ind2 is not None:
                    lnk = lnk["period"][ind2]
                    ind3 = next(i for (i, d) in enumerate(lnk["link"]) if d["type"] == "application/json")
                    lnk = requests.get(lnk["link"][ind3]["href"]).json()
                    ind4 = next(i for (i, d) in enumerate(lnk["link"]) if d["type"] == "application/json")
                    # Note, no key for data, hence always 0
                    lnk = requests.get(lnk["data"][0]["link"][ind4]["href"], timeout=10).json()

                    if lnk["value"] is not None and stn['active'] is True:
                        elem["station"] = stn["name"]
                        elem["updated"] = stn["updated"]
                        elem["lon"] = stn["longitude"]
                        elem["lat"] = stn["latitude"]
                        elem["active"] = stn["active"]
                        try:
                            # NB if we take the last element we get the latest value,
                            # the first element (0) is the oldest, the last is the youngest (in case we have a list)
                            elem["val"] = float(lnk["value"][-1]["value"])
                        except (ValueError, IndexError):
                            elem[key] = 0
                            elem["active"] = False  # Mark as inactive as we couldn't parse the value
                            if lnk["value"]:
                                logger.info("{}: {}".format(stn['name'], lnk["value"][0]["value"]))
                            else:
                                logger.info(f"{stn['name']}: lnk['value'] is empty ({lnk['value']})")

                        lst.append(elem)
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) :
                logger.info(f"Time out: {stn['name']}")
                continue
            except json.decoder.JSONDecodeError:
                logging.warning("Error decoding {} for {}".format(key, stn["name"]))
                continue

        logger.info("Exiting {}, no of stations: {}".format(key, len(lst)))

        return lst


def store(l):
    """
    Create a file such as "2019-01-18.js" and copy the file to 'weather.js'
    """
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    path = "./static/"
    name = path + l["date"] + ".json"
    with open(name, 'w') as outfile:
        json.dump(l, outfile)
        outfile.close()
        shutil.move(name, path + "weather.json")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('requests').setLevel(logging.WARNING)  # Turn off annoying logging info messages
    logging.getLogger("urllib3").setLevel(logging.WARNING)   # Turn off annoying logging info messages
    logger = logging.getLogger('collector')

    fh = RotatingFileHandler('collector.log', mode='a', maxBytes=100 * 1024 * 1024, backupCount=2)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info("Start")
    # We start 1 thread for each parameter we are collecting, the parameters is from the "smhi_keys"-dictionary
    threads = []
    for k, v in smhi_keys.items():
        threads.append(smhi_reader(k))

    for t in threads:
        t.join()  # Wait for all reading threads to terminate

    weather_data = {'date': datetime.datetime.now().isoformat()}
    i = 0
    for k, v in smhi_keys.items():
        data = threads[i].get_data()
        if data is not None:
            weather_data[k] = data
        i += 1

    store(weather_data)
    logger.info("Done")
