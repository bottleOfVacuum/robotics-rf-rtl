import socket
import cdp
import sys
import math
import _thread
import time
import datetime

# useage: python cdp_client.py lol.txt

###############################################################################
### Init connection to CUWB Server
###############################################################################
# CDP settings in CUWB manager
ip='239.255.76.67'
port=7667
# interface='10.99.51.0'
# interface='192.168.1.104'
# interface='127.0.1.1'
host_name=socket.gethostname()
host_ip=socket.gethostbyname(host_name)

# create UDP socket
listen_socket=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# bind the CUWB Network
listen_socket.bind((ip, port))

# add the socket to the multicast group 
listen_socket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(ip)+socket.inet_aton(interface))
listen_socket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(ip)+socket.inet_aton(host_ip))
###############################################################################


# variables to calculate packet 
pkg_count=0
pos_count=0
pos_count2=0
gyr_count=0
acc_count=0
qua_count=0
mag_count=0


###############################################################################
### thread to calculate packet receive every "delay" seconds
###############################################################################
def thread1(threadName, delay):
    global pkg_count, pos_count, gyr_count, acc_count, qua_count, mag_count, pos_count2
    while True:
        time.sleep(delay)
        # print("pkg, pos, gyr, acc, qua, mag: %3d, %3d, %3d, %3d, %3d, %3d" % (pkg_count, pos_count, gyr_count, acc_count, qua_count, mag_count))
        # pkg_count=pos_count=gyr_count=acc_count=qua_count=mag_count=0
        print("pos: %3d, %3d" % (pos_count, pos_count2))
        pos_count=pos_count2=0
        

### Start thread
try:
    _thread.start_new_thread(thread1, ("Thread1", 1))
except:
    print("Err: unable to start thread")
###############################################################################


###############################################################################
### store to file
###############################################################################
file_path=sys.argv[1]
f = open(file_path, "w") 
f.write("First line!\n")
###############################################################################


############################################################################
### Start receiving packet 
###############################################################################
while True:
    # Receiving CDP data on the socket
    data, address = listen_socket.recvfrom(65536)  # 2^16 is the maximum size of a CDP packet
    
    # print(data)
    # print(datetime.datetime.now())

    # decompose receive data
    cdp_packet = cdp.CDP(data)

    # PRINT "device serial number" and "packet number"
    # print(cdp_packet.serial_number, end='')
    # print(" - ", end='')    
    # print(cdp_packet.sequence)

    # search for specific tag

    if(cdp_packet.serial_number=="01:00:05CD"):

        # Data items ID codes
        #   0x0100 -> POSITION
        #   0x0009 -> GYRO
        #   0x0008 -> ACCELEROMETER
        #   0x000A -> QUATERNION
        #   0x0003 -> MAGETOMETER
        
        # pkg_count+=1

        for pos_item in cdp_packet.data_items_by_type.get(0x0100, []):                  
            pos_count+=1
        
        # for gyr_item in cdp_packet.data_items_by_type.get(0x0009, []):
        #     gyr_count+=1

        # for acc_item in cdp_packet.data_items_by_type.get(0x0008, []):
        #     acc_count+=1

        # for qua_item in cdp_packet.data_items_by_type.get(0x000A, []):
        #     qua_count+=1

        # for mag_item in cdp_packet.data_items_by_type.get(0x0003, []):
        #     mag_count+=1
            
            # print('({}, {}, {})'.format(mag_item.x, mag_item.y, mag_item.z))

         # Position
        for vals in cdp_packet.data_items_by_type.get(0x0100, []):
            tmp=str(time.time())+', 1,'+str(vals.x)+','+str(vals.y)+','+str(vals.z)+'\n'
            # sock.sendto(tmp.encode('utf-8'), caddr)
            f.write(tmp)
            f.flush()

            # print(vals)

    if(cdp_packet.serial_number=="01:00:0173"):


        for pos_item in cdp_packet.data_items_by_type.get(0x0100, []):                  
            pos_count2+=1
        
         # Position
        for vals in cdp_packet.data_items_by_type.get(0x0100, []):
            tmp=str(time.time())+', 2,'+str(vals.x)+','+str(vals.y)+','+str(vals.z)+'\n'
            # sock.sendto(tmp.encode('utf-8'), caddr)
            f.write(tmp)
            f.flush()

###############################################################################

f.close()