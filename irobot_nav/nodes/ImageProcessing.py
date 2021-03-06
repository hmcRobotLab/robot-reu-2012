#!/usr/bin/env python
import roslib; roslib.load_manifest('irobot_nav')
import rospy
import irobot_mudd
import cv_bridge
import cv
import sensor_msgs.msg as sm
from std_msgs.msg import String
from irobot_mudd.srv import *
from irobot_mudd.msg import *
import TheHive


#Get robot instance
R = TheHive.get_robot_instance()


######################### INITIALIZATION FUNCTIONS #########################

def initialize(D):
    """Creates all the images we'll need. Is separate from init_globals 
    since we need to know what size the images are before we can make
    them.
    """

    # Find the size of the image 
    # (we set D.image right before calling this function)
    D.size = cv.GetSize(D.image)

    # Create images for each color channel
    D.red = cv.CreateImage(D.size, 8, 1)
    D.green = cv.CreateImage(D.size, 8, 1)
    D.blue = cv.CreateImage(D.size, 8, 1)

    # Create images to save the thresholded images to
    D.red_threshed = cv.CreateImage(D.size, 8, 1)
    D.green_threshed = cv.CreateImage(D.size, 8, 1)
    D.blue_threshed = cv.CreateImage(D.size, 8, 1)
    D.hue_threshed = cv.CreateImage(D.size, 8, 1)
    D.sat_threshed = cv.CreateImage(D.size, 8, 1)
    D.val_threshed = cv.CreateImage(D.size, 8, 1)

    # The final thresholded result
    D.threshed_image = cv.CreateImage(D.size, 8, 1)

    # Create the hsv image
    D.hsv = cv.CreateImage(D.size, 8, 3)

    #Create hue, saturation, and value images
    D.hue = cv.CreateImage(D.size, 8, 1)
    D.sat = cv.CreateImage(D.size, 8, 1)
    D.val = cv.CreateImage(D.size, 8, 1)



################### IMAGE PROCESSING FUNCTIONS #####################

def threshold_image(D):
    """ runs the image processing in order to create a 
        black and white thresholded image out of D.image
        into D.threshed_image
    """

    # Use OpenCV to split the image up into channels,
    # saving them in their respective bw images
    cv.Split(D.image, D.blue, D.green, D.red, None)

    # This line creates a hue-saturation-value image
    cv.CvtColor(D.image, D.hsv, cv.CV_RGB2HSV)
    cv.Split(D.hsv, D.hue, D.sat, D.val, None)

    # Here is how OpenCV thresholds the images based on the slider values:
    cv.InRangeS(D.red, D.thresholds["low_red"], \
                    D.thresholds["high_red"], D.red_threshed)
    cv.InRangeS(D.green, D.thresholds["low_green"], \
                    D.thresholds["high_green"], D.green_threshed)
    cv.InRangeS(D.blue, D.thresholds["low_blue"], \
                    D.thresholds["high_blue"], D.blue_threshed)
    cv.InRangeS(D.hue, D.thresholds["low_hue"], \
                    D.thresholds["high_hue"], D.hue_threshed)
    cv.InRangeS(D.sat, D.thresholds["low_sat"], \
                    D.thresholds["high_sat"], D.sat_threshed)
    cv.InRangeS(D.val, D.thresholds["low_val"], \
                    D.thresholds["high_val"], D.val_threshed)
                                                   

    # Multiply all the thresholded images into one "output" image,
    # named D.threshed_image"]
    cv.Mul(D.red_threshed, D.green_threshed, D.threshed_image)
    cv.Mul(D.threshed_image, D.blue_threshed, D.threshed_image)
    cv.Mul(D.threshed_image, D.hue_threshed, D.threshed_image)
    cv.Mul(D.threshed_image, D.sat_threshed, D.threshed_image)
    cv.Mul(D.threshed_image, D.val_threshed, D.threshed_image)

    # Erode and Dilate shave off and add edge pixels respectively
    cv.Erode(D.threshed_image, D.threshed_image, iterations = 1)
    cv.Dilate(D.threshed_image, D.threshed_image, iterations = 1)


def find_biggest_region(D):
    """ finds all the contours in threshed image, finds the largest of those,
        and then marks in in the main image
    """

    # Create a copy image of thresholds then find contours on that image
    storage = cv.CreateMemStorage(0) # Create memory storage for contours
    copy = cv.CreateImage(D.size, 8, 1)
    cv.Copy( D.threshed_image, copy ) # copy threshed image

    # this is OpenCV's call to find all of the contours:
    contours = cv.FindContours(copy, storage, cv.CV_RETR_EXTERNAL, \
                                   cv.CV_CHAIN_APPROX_SIMPLE)

    # Next we want to find the *largest* contour
    if len(contours) > 0:
        biggest = contours
        biggestArea = cv.ContourArea(contours)
        while contours != None:
            nextArea = cv.ContourArea(contours)
            if biggestArea < nextArea:
                biggest = contours
                biggestArea = nextArea
            contours = contours.h_next()
        
        # Use OpenCV to get a bounding rectangle for the largest contour
        br = cv.BoundingRect(biggest, update=0)

        #print "in find_regions, br is", br

	ulx, uly, width, height = br[0], br[1], br[2], br[3]

	D.br = (ulx, uly), (width, height)
	D.target_size = width * height

        # You will want to change these so that they draw a box
        # around the largest contour and a circle at its center:

        # Example of drawing a yellow box
        cv.PolyLine(D.image, [[(ulx,uly), (ulx+width,uly), (ulx+width,uly+height),\
			    (ulx,uly+height)]], 1, cv.RGB(255, 255, 0))

        # Draw circle in the center of the target
        cv.Circle(D.image, (ulx+width/2,uly+height/2), 10, \
                      cv.RGB(255, 0, 0), thickness=1, lineType=8, shift=0)

        # Draw the contours in white with inner ones in green
        cv.DrawContours(D.image, biggest, cv.RGB(255, 255, 255), \
                            cv.RGB(0, 255, 0), 1, thickness=2, lineType=8, \
                            offset=(0,0))
	
	# Reset coordinates to keep track of where the center of the coutour is
	D.last_target_coord = D.target_coord
	D.target_coord = (ulx+width/2,uly-height/2)
	D.p1, D.p2, D.p3, D.p4 = (D.target_coord[0],D.target_coord[1] + height/2),\
				 (D.target_coord[0],D.target_coord[1] + height/2), \
				 (D.target_coord[0],D.target_coord[1] + height/2), \
				 (D.target_coord[0],D.target_coord[1] + height/2)
    else:
	D.br = (0,0),(0,0)
	D.target_size = 0
	D.p1, D.p2, D.p3, D.p4 = (0,0),(0,0),(0,0),(0,0)
	
def mouse_section(D):
    """Displays a rectangle defined by dragging the mouse."""

    if D.mouse_down:
        x0 = D.down_coord[0]
        y0 = D.down_coord[1]
        x1 = D.up_coord[0]
        y1 = D.up_coord[1]
        cv.PolyLine(D.image, [[(x0,y0), (x0,y1), (x1,y1), (x1,y0)]], 1, cv.RGB(0, 255, 0))



def process_section(D):
    """Calculates the min/max slider values for a given section and sets the
        slider values to them.
    """

    print "sections:", D.sections
    
    D.collecting_M= { 'high_green':0, 'low_green':255,\
                         'low_blue':255, 'low_val':255,\
                         'high_hue':0, 'high_val':0,\
                         'low_hue':255, 'high_blue':0,\
                         'low_red':255,'high_red':0,\
                         'high_sat':0, 'low_sat':255}
	    
    if len(D.sections) > 0:
	# pull out all sections with 'a' in the front
        adds = [[x[1], x[2]] for x in D.sections if x[0] == 'a']
	# pull out all sections with a 's' in the front
        subs = [[x[1], x[2]] for x in D.sections if x[0] == 's']
	
	print "adds are", adds
	print "subs are", subs

	for sect in range(0, len(adds)):
	    userTopLeft = adds[sect][0]
	    userBotRight = adds[sect][1]
	    
	    # If we need to subtract an area
	    if len(subs) > 0:

	        for x in range(userTopLeft[0], userBotRight[0]):
		    for y in range(userTopLeft[1],userBotRight[1]):
		        for subSect in range(0, len(subs)):
			    
			    subXMin = subs[subSect][0][0]
			    subXMax = subs[subSect][1][0]
			    subYMin = subs[subSect][1][1]
			    subYMax = subs[subSect][0][1]
			    
			    if (x < subXMax and x > subXMin) or \
						(y <subYMax and y > subYMin):
				pass
			    else:
			        (b,g,r) = D.image[y,x]
			        (h,s,v) = D.hsv[y,x]
			        color = { "blue": b, "green": g, "red": r, "hue": h, "sat":s, "val":v}
			        for name in color:
				    high_name = "high_" + name
				    low_name = "low_" + name
				    if color[name] > D.collecting_M[high_name]:
					D.collecting_M[high_name] = color[name]
				    if color[name] < D.collecting_M[low_name]:
					D.collecting_M[low_name] = color[name]
				    else:
					pass
				    
	    #If we only add areas
	    else:

		for x in range(userTopLeft[0], userBotRight[0]):
		    for y in range(userTopLeft[1],userBotRight[1]):
			
			(b,g,r) = D.image[y,x]
			(h,s,v) = D.hsv[y,x]
			color = { "blue": b, "green": g, "red": r, "hue": h, "sat":s, "val":v}
			
			for name in color:

			    high_name = "high_" + name
			    low_name = "low_" + name
			    
			    if color[name] > D.collecting_M[high_name]:
				D.collecting_M[high_name] = color[name]
				
			    if color[name] < D.collecting_M[low_name]:
				D.collecting_M[low_name] = color[name]
				
			    else:
				pass


	# Now reset sliders to the found max and min
	D.thresholds = D.collecting_M
	"""
	for i in D.thresholds:
	    cv.SetTrackbarPos(i, 'Sliders', int(D.collecting_M[i]))
	"""


def target_coord(D):
    """Displays a circle around the target coordinate on the image."""
    (x,y) = D.target_coord
    cv.Circle(D.image, (x,y), 10, cv.RGB(255, 0, 255), thickness=3, lineType=8, shift=0)




def draw_on_image(D):
    """Displays an info box and necessary text in the image window."""
    #Set up rectangle's position within window
    lower_left_x = 20                           
    lower_left_y = 42
    dx = 5
    dy = 5

    #Display border for rectangle
    #Border is a black rectangle under white text rectangle
    bord_upper_left = (lower_left_x-dx-3, lower_left_y-dy-20-3)
    bord_lower_right = (lower_left_x+dx+160+3, lower_left_y+dy+50+3)
    cv.Rectangle(D.image, bord_upper_left, bord_lower_right, D.black, cv.CV_FILLED)
    
    #Display white rectangle under text
    rect_upper_left = (lower_left_x-dx, lower_left_y-dy-20)
    rect_lower_right = (lower_left_x+dx+160, lower_left_y+dy+50)
    cv.Rectangle(D.image, rect_upper_left, rect_lower_right, D.white, cv.CV_FILLED)
  
    # Build Strings
    targetA = ("Target Area: %.lf" % D.target_size)                         
    targetCoords = ("Distance: %.lf " % 4)
    state = ("Current State: "+ R.curState )
    
    # Position strings in a box so they won't overlap
    firstLineString = (lower_left_x,lower_left_y)               
    secondLineString = (lower_left_x, lower_left_y + 20)          
    thirdLineString = (lower_left_x, lower_left_y + 40)
    #desiredHeading = ("Des: %.2f" % desHeadVar)   
    cv.PutText(D.image, targetA, firstLineString, D.font, cv.RGB(0,0,255))       
    cv.PutText(D.image, targetCoords, secondLineString, D.font, cv.RGB(0,0,255))
    cv.PutText(D.image, state, thirdLineString, D.font, cv.RGB(0,0,255))

    #cv.PutText(D.image, desiredHeading, thirdLineString, D.font, cv.RGB(0,0,255))
    
    cv.Circle(D.image, (320,240), 10,cv.RGB(255, 0, 0), thickness=1, lineType=8, shift=0)
	
	
	
################# END IMAGE PROCESSING FUNCTIONS ###################



