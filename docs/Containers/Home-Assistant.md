# Home Assistant

Home Assistant is a home automation platform running on Python 3. It is able to track and control all devices at your home and offer a platform for automating control.

## References

- [Home Assistant home page](https://www.home-assistant.io/)

	- [Raspberry Pi installation](https://www.home-assistant.io/installation/raspberrypi/)
	- [General installation](https://www.home-assistant.io/installation) (may be useful if you are trying to run on other hardware).

- [GitHub repository](https://github.com/home-assistant/core)
- [DockerHub](https://hub.docker.com/r/homeassistant/home-assistant/)


## <a name="twoVersions">Home Assistant: two versions</a>

There are two versions of Home Assistant:

* Hass.io (Home Assistant Core), and
* Home Assistant Container.

Each version:

* provides a web-based management interface on port 8123; and
* runs in "host mode" in order to discover devices on your LAN, including devices communicating via multicast traffic.

IOTstack allows you to **install** either, or both, versions.

Note:

* Technically, both versions can **run** at the same time but it is not **supported**. Each version runs in "host mode" and binds to port 8123 so, in practice, the first version to start will claim the port and the second version will then be blocked.

### Hass.io

Hass.io uses its own orchestration:

* hassio\_supervisor
* hassio\_audio
* hassio\_cli
* hassio\_dns
* hassio\_multicast
* hassio\_observer
* homeassistant.

IOTstack can only offer limited configuration of Hass.io since it is its own platform.

### Home Assistant Container

Home Assistant Container runs as a single Docker container, and doesn't support all the features that Hass.io does (such as add-ons).

## Menu installation

### Installing Hass.io

Hass.io creates a conundrum:

* If you are definitely going to install Hass.io then you **must** install its dependencies **before** you install Docker.
* One of Hass.io's dependencies is [Network Manager](https://wiki.archlinux.org/index.php/NetworkManager). Network Manager makes **serious** changes to your operating system, with side-effects you may not expect such as giving your Raspberry Pi's WiFi interface a random MAC address both during the installation and, then, each time you reboot. You are in for a world of pain if you install Network Manager without first understanding what is going to happen and planning accordingly.
* If you don't install Hass.io's dependencies before you install Docker, you will either have to uninstall Docker or rebuild your system. This is because both Docker and Network Manager adjust your Raspberry Pi's networking. Docker is happy to install after Network Manager, but the reverse is not true.

#### Step 1: If Docker is already installed, uninstall it

```bash
$ sudo apt -y purge docker-ce docker-ce-cli containerd.io
$ sudo apt -y remove docker-compose
$ sudo pip3 uninstall docker-compose
```

Note:

* Removing Docker does **not** interfere with your existing `~/IOTstack` folder.

#### Step 2: Ensure your system is fully up-to-date

```bash
$ sudo apt update
$ sudo apt upgrade -y
```

#### Step 3: Install Hass.io dependencies (stage 1)

```bash
$ sudo apt install -y apparmor apparmor-profiles apparmor-utils
$ sudo apt install -y software-properties-common apt-transport-https ca-certificates dbus
```

#### Step 4: Connect to your Raspberry Pi via Ethernet

You can skip this step if you interact with your Raspberry Pi via a screen connected to its HDMI port, along with a keyboard and mouse.

If, however, you are running "headless" (SSH or VNC), we **strongly recommend** connecting your Raspberry Pi to Ethernet. This is only a temporary requirement. You can return to WiFi-only operation after Hass.io is installed.

When the Ethernet interface initialises, work out its IP address:

```bash
$ ifconfig eth0

eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 192.168.132.9  netmask 255.255.255.0  broadcast 192.168.132.255
        ether ab:cd:ef:12:34:56  txqueuelen 1000  (Ethernet)
        RX packets 4166292  bytes 3545370373 (3.3 GiB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 2086814  bytes 2024386593 (1.8 GiB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
```   

In the above, the IP address assigned to the Ethernet interface is on the second line of output, to the right of "inet": 192.168.132.9.

Drop out of your existing session (SSH or VNC) and re-connect to your Raspberry Pi using the IP address assigned to its Ethernet interface:

```bash
$ ssh pi@192.168.132.9
```

or:

```
vnc://pi@192.168.132.9
```

The reason for stipulating the IP address, rather than a name like `raspberrypi.local` is so that you are *definitely* connected to the Ethernet interface.

If you ignore the advice about connecting via Ethernet and install Network Manager while your session is connected via WiFi, your connection will freeze part way through the installation (when Network Manager starts running and unconditionally changes your Raspberry Pi's WiFi MAC address).

You *may* be able to re-connect after the WiFi interface acquires a new IP address and advertises that via multicast DNS associated with the name of your device (eg `raspberrypi.local`), but you may also find that the only way to regain control is to power-cycle your Raspberry Pi.

The advice about using Ethernet is well-intentioned. You should heed this advice even if means you need to temporarily relocate your Raspberry Pi just so you can attach it via Ethernet for the next few steps. You can go back to WiFi later, once everything is set up. You have been warned!

#### Step 5: Install Hass.io dependencies (stage 2)

Install Network Manager:

```bash
$ sudo apt install -y network-manager
```

#### Step 6: Consider disabling random MAC address allocation

To understand why you should consider disabling random MAC address allocation, see [why random MACs are such a hassle ](#why-random-macs-are-such-a-hassle).

You can stop Network Manager from allocating random MAC addresses to your WiFi interface by running the following commands:

```bash
$ sudo sed -i.bak '$a\\n[device]\nwifi.scan-rand-mac-address=no\n' /etc/NetworkManager/NetworkManager.conf
$ sudo systemctl restart NetworkManager.service
```

Acknowledgement:

* This tip came from [@steveatk on Discord](https://discordapp.com/channels/638610460567928832/638610461109256194/758825690715652116).

#### Step 7: Re-install Docker

You can re-install Docker using the IOTstack menu or one of the scripts provided with IOTstack but the following commands guarantee an up-to-date version of `docker-compose` and also include a dependency needed if you want to run with the 64-bit kernel:

```bash
$ curl -fsSL https://get.docker.com | sh
$ sudo usermod -G docker -a $USER
$ sudo usermod -G bluetooth -a $USER
$ sudo apt install -y python3-pip python3-dev
$ [ "$(uname -m)" = "aarch64" ] && sudo apt install libffi-dev
$ sudo pip3 install -U docker-compose
$ sudo pip3 install -U ruamel.yaml==0.16.12 blessed
$ sudo reboot
```

Note:

* Installing or re-installing Docker does **not** interfere with your existing `~/IOTstack` folder.

#### Step 8: Run the Hass.io installation

Start at:

```bash
$ cd ~/IOTstack
$ ./menu.sh
```

Hass.io installation can be found inside the `Native Installs` menu on the main menu. You will be asked to select your device type during the installation.

The installation of Hass.io takes up to 20 minutes (depending on your internet connection). You may also need to respond "Y" to a prompt during the installation process. Refrain from restarting your machine until it has come online and you are able to create a user account.

Hass.io installation is provided as a convenience. It is independent of, is not maintained by, and does not appear in the `docker-compose.yml` for IOTstack. Hass.io has its own service for maintaining its uptime.

#### Re-check random MAC address allocation

Installing Hass.io can re-enable random MAC address allocation. You should check this via:

```bash
$ tail -3 /etc/NetworkManager/NetworkManager.conf
[device]
wifi.scan-rand-mac-address=no

```

If you do **NOT** see `wifi.scan-rand-mac-address=no`, repeat [Step 6](#step-6-consider-disabling-random-mac-address-allocation).

### Installing Home Assistant Container

Home Assistant can be found in the `Build Stack` menu. Selecting it in this menu results in a service definition being added to:

```
~/IOTstack/docker-compose.yml
```

When you choose "Home Assistant", the service definition added to your `docker-compose.yml` includes the following:

```yaml
image: ghcr.io/home-assistant/home-assistant:stable
#image: ghcr.io/home-assistant/raspberrypi3-homeassistant:stable
#image: ghcr.io/home-assistant/raspberrypi4-homeassistant:stable
```

The active image is *generic* in the sense that it should work on any platform. You may wish to edit your `docker-compose.yml` to deactivate the generic image in favour of an image tailored to your hardware.

The normal IOTstack commands apply to Home Assistant Container such as:

```bash
$ cd ~/IOTstack
$ docker-compose up -d
```

## HTTPS with a valid certificate

Some HA integrations (e.g google assistant) require your HA API to be
accessible via https with a valid certificate. You can configure HA to do this:
[docs](https://www.home-assistant.io/docs/configuration/remote/) /
[guide](https://www.home-assistant.io/docs/ecosystem/certificates/lets_encrypt/)
or use a reverse proxy container, as described below.

The linuxserver Secure Web Access Gateway container
([swag](https://docs.linuxserver.io/general/swag)) ([Docker hub
docs](https://hub.docker.com/r/linuxserver/swag)) will automatically generate a
SSL-certificate, update the SSL certificate before it expires and act as a
reverse proxy.

1. First test your HA is working correctly: `http://raspberrypi.local:8123/` (assuming
your RPi hostname is raspberrypi)
2. Make sure you have duckdns working.
3. On your internet router, forward public port 443 to the RPi port 443
4. Add swag to ~/IOTstack/docker-compose.yml beneath the `services:`-line:
```
  swag:
    image: ghcr.io/linuxserver/swag
    cap_add:
      - NET_ADMIN
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
      - URL=<yourdomain>.duckdns.org
      - SUBDOMAINS=wildcard
      - VALIDATION=duckdns
      - DUCKDNSTOKEN=<token>
      - CERTPROVIDER=zerossl
      - EMAIL=<e-mail> # required when using zerossl
    volumes:
      - ./volumes/swag/config:/config
    ports:
      - 443:443
    restart: unless-stopped
```
    Replace the bracketed values. Do NOT use any "-characters to enclose the values.

5. Start the swag container, this creates the file to be edited in the next step:
   ```
   cd ~/IOTstack && docker-compose up -d
   ```

    Check it starts up OK: `docker-compose logs -f swag`. It will take a minute or two before it finally logs "Server ready".

6. Enable reverse proxy for `raspberrypi.local`. `homassistant.*` is already by default. and fix homeassistant container name ("upstream_app"):
      ```
      sed -e 's/server_name/server_name *.local/' \
          volumes/swag/config/nginx/proxy-confs/homeassistant.subdomain.conf.sample \
          > volumes/swag/config/nginx/proxy-confs/homeassistant.subdomain.conf
      ```

7. Forward to correct IP when target is a container running in "network_mode:
   host" (like Home Assistant does):
   ```
   cat << 'EOF' | sudo tee volumes/swag/config/custom-cont-init.d/add-host.docker.internal.sh
   #!/bin/sh
   DOCKER_GW=$(ip route | awk 'NR==1 {print $3}')

   sed -i -e "s/upstream_app .*/upstream_app ${DOCKER_GW};/" \
       /config/nginx/proxy-confs/homeassistant.subdomain.conf
   EOF
   sudo chmod u+x volumes/swag/config/custom-cont-init.d/add-host.docker.internal.sh
   ```
   (This needs to be copy-pasted/entered as-is, ignore any "> "-prefixes printed
   by bash)

8. (optional) Add reverse proxy password protection if you don't want to rely
   on the HA login for security, doesn't affect API-access:
    ```
    sed -i -e 's/#auth_basic/auth_basic/' \
        volumes/swag/config/nginx/proxy-confs/homeassistant.subdomain.conf
    docker-compose exec swag htpasswd -c /config/nginx/.htpasswd anyusername
    ```
9. Add `use_x_forwarded_for` and `trusted_proxies` to your homeassistant [http
   config](https://www.home-assistant.io/integrations/http). The configuration
   file is at `volumes/home_assistant/configuration.yaml` For a default install
   the resulting http-section should be:
   ```
   http:
      use_x_forwarded_for: true
      trusted_proxies:
        - 192.168.0.0/16
        - 172.16.0.0/12
        - 10.77.0.0/16
   ```
10. Refresh the stack: `cd ~/IOTstack && docker-compose stop && docker-compose
    up -d` (again may take 1-3 minutes for swag to start if it recreates
    certificates)
11. Test homeassistant is still working correctly:
    `http://raspberrypi.local:8123/` (assuming your RPi hostname is
    raspberrypi)
12. Test the reverse proxy https is working correctly:
    `https://raspberrypi.local/` (browser will issue a warning about wrong
    certificate domain, as the certificate is issued for you duckdns-domain, we
    are just testing)

    Or from the command line in the RPi:
    ```
    curl --resolve homeassistant.<yourdomain>.duckdns.org:443:127.0.0.1 \
        https://homeassistant.<yourdomain>.duckdns.org/
    ```
    (output should end in `if (!window.latestJS) { }</script></body></html>`)

13. And finally test your router forwards correctly by accessing it from
    outside your LAN(e.g. using a mobile phone):
    `https://homeassistant.<yourdomain>.duckdns.org/` Now the certificate
    should work without any warnings.

## Deactivating Hass.io

Because Hass.io is independent of IOTstack, you can't deactivate it with any of the commands you normally use for IOTstack.

To deactivate Hass.io you first need to stop the service that controls it. Run the following commands in the terminal: 

```bash
$ sudo systemctl stop hassio-supervisor.service
$ sudo systemctl disable hassio-supervisor.service
```

This will stop the main service and prevent it from starting on the next boot. Next you need to stop and remove the dependent services:

```bash
$ docker stop hassio_audio hassio_cli hassio_dns hassio_multicast hassio_observer homeassistant
$ docker rm hassio_audio hassio_cli hassio_dns hassio_multicast hassio_observer homeassistant 
```

Double-check with `docker ps` to see if there are other containers running with a `hassio_` prefix. They can stopped and removed in the same fashion for `hassio_audio` and so-on.

The stored files are located in `/usr/share/hassio` which can be removed if you need to.

You can use Portainer to view what is running and clean up the unused images.

At this point, Hass.io is stopped and will not start again after a reboot. Your options are:

* Leave things as they are; or
* Re-install Hass.io by starting over at [Installing Hass.io](#installing-hassio); or
* Re-activate Hass.io by:

	```bash
	$ sudo systemctl enable hassio-supervisor.service
	$ sudo systemctl start hassio-supervisor.service
	```

## Why random MACs are such a hassle

> This material was originally posted as part of [Issue 312](https://github.com/SensorsIot/IOTstack/issues/312). It was moved here following a suggestion by [lole-elol](https://github.com/lole-elol).

When you connect to a Raspberry Pi via SSH (Secure Shell), that's a layer 7 protocol that is riding on top of TCP/IP. TCP (Transmission Control Protocol) is a layer 4 connection-oriented protocol which rides on IP (Internet Protocol) which is a layer 3 protocol. So far, so good.

But you also need to know what happens at layers 2 and 1. When your SSH client (eg Mac or PC or another Unix box) opens its SSH connection, at layer 3 the IP stack applies the subnet mask against the IP addresses of both the source device (your Mac, PC, etc) and destination device (Raspberry Pi) to split them into "network portion" (on the left) and "host portion" on the right. It then compares the two network portions and, if they are the same, it says "local network".

> To complete the picture, if they do not compare the same, then IP substitutes the so-called "default gateway" address (ie your router) and repeats the mask-and-compare process which, unless something is seriously mis-configured, will result in those comparing the same and being "local network". This is why data-comms gurus sometimes say, "all networking is local".

What happens next depends on the data communications media but we'll assume Ethernet and WiFi seeing as they are pretty much interchangeable for our purposes.

The source machine (Mac, PC, etc) issues an ARP (address resolution protocol). It is a broadcast frame (we talk about "frames" rather than "packets" at Layer 2) asking the question, "who has this destination IP address?" The Raspberry Pi responds with a unicast packet saying, "that's me" and part of that includes the MAC (media access control) address of the Raspberry Pi. The source machine only does this **once** (and this is a key point). It assumes the relationship between IP address and MAC address will not change and it adds the relationship to its "ARP cache". You can see the cache on any Unix computer with:

```bash
$ arp -a
```

The Raspberry Pi makes the same assumption: it has learned both the IP and MAC address of the source machine (Mac, PC, etc) from the ARP request and has added that to its own ARP cache.

In addition, every layer two switch (got one of those in your home?) has been snooping on this traffic and has learned, for each of its ports, which MAC address(es) are on those ports.

Not "MAC **and** IP". A switch works at Layer 2. All it sees are frames. It only caches MAC addresses!

When the switch saw the "who has?" ARP broadcast, it replicated that out of all of its ports but when the "that's me" came back from the Raspberry Pi as a unicast response, it only went out on the switch port where the source machine (Mac, PC, etc) was attached.

After that, it's all caching. The Mac or PC has a packet to send to the Pi. It finds the hit in its ARP cache, wraps the packet in a frame and sends it out its Ethernet or WiFi interface. Any switches receive the frame, consult their own tables, and send the frame out the port on the next hop to the destination device. It doesn't matter whether you have one switch or several in a cascade, they have all learned the "next hop" to each destination MAC address they have seen. 

Ditto when the Pi sends back any reply packets. ARP. Switch. Mac/PC. All cached.

The same basic principles apply, irrespective of whether the "switching function" is wired (Ethernet) or WiFi, so it doesn't really matter if your home arrangement is as straightforward as Mac or PC and Pi, both WiFi, via a local WiFi "hub" which is either standalone or part of your router. If something is capable of learning where a MAC is, it does.

Still so far so good.

Now comes the problem. You have established an SSH session connected to the Pi over its WiFi interface. You install Network Manager. As part of its setup, Network Manager discards the **fixed** MAC address which is burned into the Pi's WiFi interface and substitutes a randomly generated MAC address. It doesn't ask for permission to do that. It doesn't warn you it's about to do it. It just does it.

When the WiFi interface comes up, it almost certainly "speaks" straight away via DHCP to ask for an IP address. The DHCP server looks in its own table of MAC-to-IP associations (fixed or dynamic, doesn't matter) and says "never seen **that** MAC before - here's a brand new IP address lease".

The DHCP request is broadcast so all the switches will have learned the new MAC but they'll also still have the old MAC (until it times out). The Mac/PC will receive the DHCP broadcast but, unless it's the DHCP server, will discard it. Either way, it has no means of knowing that this new random MAC belongs to the Pi so it can't do anything sensible with the information.

Meanwhile, SSH is trying to keep the session alive. It still thinks "old IP address" and its ARP cache still thinks old IP belongs to old MAC. Switches know where the frames are meant to go but even if a frame does get somewhere near the Pi, the Pi's NIC (network interface card) ignores it because it's now the wrong destination MAC. The upshot is that SSH looks like the session has frozen and it will eventually time-out with a broken pipe.

To summarise: Network Manager has changed the MAC without so much as a by-your-leave and, unless you have assigned static IP addresses **in the Raspberry Pi** it's quite likely that the Pi will have a different IP address as well. But even a static IP can't save you from the machinations of Network Manager!

The Pi is as happy as the proverbial Larry. It goes on, blissfully unaware that it has just confused the heck out of everything else. You can speed-up some of the activities that need to happen before everything gets going again. You can do things like clear the old entry from the ARP cache on the Mac/PC. You can try to force a multicast DNS daemon restart so that the "raspberrypi.local" address gets updated more quickly but mDNS is a distributed database so it can be hit and miss (and can sometimes lead to complaints about two devices trying to use the same name). Usually, the most effective thing you can do is pull power from the Pi, reboot your Mac/PC (easiest way to clear its ARP cache) and then apply power to the Pi so that it announces its mDNS address at the right time for the newly-booted Mac/PC to hear it and update its mDNS records. 

That's why the installation advice says words to the effect of:

> whatever else you do, **don't** try to install Network Manager while you're connected over WiFi. If SSH is how you're going to do it, you're in for a world of pain if you don't run an Ethernet cable for at least that part of the process.

And it does get worse, of course. Installing Network Manager turns on random WiFi MAC. You can turn it off and go back to the fixed MAC. But then, when you install Docker, it happens again. It may also be that other packages come along in future and say, "hey, look, Network Manager is installed - let's take advantage of that" and it happens again when you least expect it.

Devices changing their MACs at random is becoming reasonably common. If you have a mobile device running a reasonably current OS, it is probably changing its MAC all the time. The idea is to make it hard for Fred's Corner Store to track you and conclude, "Hey, Alex is back in the shop again."

Random MACs are not a problem for a **client** device like a phone, tablet or laptop. But they are definitely a serious problem for a **server** device.

> In TCP/IP any device can be a client or a server for any protocol. The distinction here is about *typical* use. A mobile device is not usually set up to *offer* services like MQTT or Node-RED. It typically *initiates* connections with servers like Docker containers running on a Raspberry Pi.

It is not just configuration-time SSH sessions that break. If you decide to leave Raspberry Pi random Wifi MAC active **and** you have other clients (eq IoT devices) communicating with the Pi over WiFi, you will wrong-foot those clients each time the Raspberry Pi reboots. Data communications services from those clients will be impacted until those client devices time-out and catch up.
