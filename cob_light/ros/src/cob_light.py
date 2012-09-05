#!/usr/bin/python
#***************************************************************
#
# Copyright (c) 2010
#
# Fraunhofer Institute for Manufacturing Engineering	
# and Automation (IPA)
#
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#
# Project name: care-o-bot
# ROS stack name: cob_driver
# ROS package name: cob_light
#								
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#			
# Author: Florian Weisshardt, email:florian.weisshardt@ipa.fhg.de
# Supervised by: Florian Weisshardt, email:florian.weisshardt@ipa.fhg.de
# Modified by: Benjamin Maidel, email:benjamin.maidel@ipa.fhg.de
#
# Date of creation: June 2010
# ToDo:
#
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Fraunhofer Institute for Manufacturing 
#       Engineering and Automation (IPA) nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License LGPL as 
# published by the Free Software Foundation, either version 3 of the 
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License LGPL for more details.
# 
# You should have received a copy of the GNU Lesser General Public 
# License LGPL along with this program. 
# If not, see <http://www.gnu.org/licenses/>.
#
#****************************************************************

import roslib; 
roslib.load_manifest('cob_light')
import rospy
from std_msgs.msg import ColorRGBA
from cob_light.srv import *
from visualization_msgs.msg import Marker

import serial
import sys
import math

class LedMode:
	(STATIC, BREATH, FLASH) = range(0,3)

class LightControl:
	def __init__(self):
		self.ns_global_prefix = "/light_controller"
		self.pub_marker = rospy.Publisher("marker", Marker)
		# set default color to green rgba = [0,1,0,1]
		self.color = ColorRGBA()
		self.color.r = 0
		self.color.g = 1
		self.color.b = 0
		self.color.a = 1
		self.sim_mode = False
        
		self.ser = None
		self.handle_timer = None
		self.inc_timer = 0.0

		# get parameter from parameter server
		if not self.sim_mode:
			if not rospy.has_param(self.ns_global_prefix + "/devicestring"):
				rospy.logwarn("parameter %s does not exist on ROS Parameter Server, aborting... (running in simulated mode)",self.ns_global_prefix + "/devicestring")
				self.sim_mode = True
			devicestring_param = rospy.get_param(self.ns_global_prefix + "/devicestring")
		
		if not self.sim_mode:
			if not rospy.has_param(self.ns_global_prefix + "/baudrate"):
				rospy.logwarn("parameter %s does not exist on ROS Parameter Server, aborting... (running in simulated mode)",self.ns_global_prefix + "/baudrate")
				self.sim_mode = True
			baudrate_param = rospy.get_param(self.ns_global_prefix + "/baudrate")
		
		if not self.sim_mode:
			# open serial communication
			rospy.loginfo("trying to initializing serial connection")
			try:
				self.ser = serial.Serial("/dev/ttyUSB0", baudrate_param)
			except serial.serialutil.SerialException:
				rospy.logwarn("Could not initialize serial connection on %s, aborting... (running in simulated mode)",devicestring_param)
				self.sim_mode = True
			if not self.sim_mode:
				rospy.loginfo("serial connection on %s initialized successfully", devicestring_param)

	def setRGB(self, color):
		#check if timer function is running
		if self.handle_timer is not None:
			self.handle_timer.shutdown()
			self.handle_timer = None
		#color in rgb color space ranging from 0 to 999
		# check range and send to serial bus
		if(color.r <= 1 and color.g <= 1 and color.b <= 1):
			#scale from 0 to 999
			red = (1-color.r)*999.0
			green = (1-color.g)*999.0
			blue = (1-color.b)*999.0
			rospy.loginfo("send color to microcontroller: rgb = [%d, %d, %d]", red, green, blue)
			self.ser.write(str(int(red))+ " " + str(int(green))+ " " + str(int(blue))+"\n\r")
		else:
			rospy.logwarn("Color not in range 0...1 color: rgb = [%d, %d, %d] a = [%d]", color.r, color.g, color.b, color.a)

	def ModeCallback(self, req):
		res = LightModeResponse()
		self.color = req.color
		self.setRGB(self.color)
		if req.mode == LedMode.BREATH:
			rospy.loginfo("Set mode to Breath")
			if self.handle_timer is not None:
				self.handle_timer.shutdown()
			self.inc_timer = 0.0
			self.handle_timer = rospy.Timer(rospy.Duration(0.05), self.BreathTimerEvent)
			res.error_type = 0
			res.error_msg = ""
		elif req.mode == LedMode.STATIC:
			rospy.loginfo("Set mode to Static")
			if self.handle_timer is not None:
				self.handle_timer.shutdown()
				self.handle_timer = None
				res.error_type = 0
				res.error_msg=""
		elif req.mode == LedMode.FLASH:
			rospy.loginfo("Set mode to Flash")
			if self.handle_timer is not None:
				self.handle_timer.shutdown()
				self.handle_timer = None
				res.error_type = 0
				res.error_msg = ""
		else:
			rospy.logwarn("Unsupported Led Mode: %d",mode)
			res.error_type = -1
			res.error_msg = "Unsupported Led Mode requested"
		return res

	def BreathTimerEvent(self, event):
		fV = math.sin(self.inc_timer)
		#breathing function simple: e^sin(x) and then from 0 to 1
		#fkt: (exp(sin(x))-1/e)*(999/(e-1/e))
		fV = (math.exp(math.sin(self.inc_timer*math.pi))-0.36787944)*425.03360505
		self.inc_timer += 0.01
		if self.inc_timer >= 2.0:
			self.inc_timer = 0.0
		red = math.fabs((self.color.r * fV))#*999.0)
		green = math.fabs((self.color.g * fV))#*999.0)
		blue = math.fabs((self.color.b * fV))#*999.0)
		red = 999.0 - red
		green = 999.0 - green
		blue = 999.0 - blue
		if self.ser is not None:
			self.ser.write(str(int(red))+ " " + str(int(green)) + " " + str(int(blue))+"\n\r")
		else:
			rospy.loginfo("Setting color to: rgb [%d, %d, %d]", red, green, blue)
	

	def publish_marker(self):
		# create marker
		marker = Marker()
		marker.header.frame_id = "/base_link"
		marker.header.stamp = rospy.Time.now()
		marker.ns = "color"
		marker.id = 0
		marker.type = 2 # SPHERE
		marker.action = 0 # ADD
		marker.pose.position.x = 0
		marker.pose.position.y = 0
		marker.pose.position.z = 1.5
		marker.pose.orientation.x = 0.0
		marker.pose.orientation.y = 0.0
		marker.pose.orientation.z = 0.0
		marker.pose.orientation.w = 1.0
		marker.scale.x = 0.1
		marker.scale.y = 0.1
		marker.scale.z = 0.1
		marker.color.a = self.color.a #Transparency
		marker.color.r = self.color.r
		marker.color.g = self.color.g
		marker.color.b = self.color.b
		# publish marker
		self.pub_marker.publish(marker)

	def LightCallback(self,color):
		rospy.loginfo("Received new color: rgb = [%d, %d, %d] a = [%d]", color.r, color.g, color.b, color.a)
		self.color = color
		if not self.sim_mode:
			self.setRGB(color)

if __name__ == '__main__':
	rospy.init_node('light_controller')
	lc = LightControl()
	rospy.Subscriber("command", ColorRGBA, lc.LightCallback)
	rospy.Service('mode', LightMode, lc.ModeCallback)
	if not lc.sim_mode:
		rospy.loginfo(rospy.get_name() + " running")
	else:
		rospy.loginfo(rospy.get_name() + " running in simulated mode")
		
	r = rospy.Rate(10)
	while not rospy.is_shutdown():
		lc.publish_marker()
		r.sleep()
