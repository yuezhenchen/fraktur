# Christine Yang
# Fraktur Cracker
# seg_the_third.py
# third attempt at character segmentation, using OpenCV

# OPENCV
# https://stackoverflow.com/questions/49291770/ocr-cropping-the-letters
# https://stackoverflow.com/questions/42316315/how-to-segment-license-plate-characters-removing-unwanted-characters-using-openc
# https://docs.opencv.org/3.4/dd/d49/tutorial_py_contour_features.html
# https://circuitdigest.com/tutorial/image-segmentation-using-opencv
# https://stackoverflow.com/questions/28759253/how-to-crop-the-internal-area-of-a-contour
# https://docs.opencv.org/master/d7/d4d/tutorial_py_thresholding.html
# https://stackoverflow.com/questions/50432349/combine-contours-vertically-and-get-convex-hull-opencv-python
# ROI = region of interest

# thresh = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 1)

import os, codecs, numpy as np, cv2, re
from preprocess import preprocess

your_path_here = '/Users/ovoowo/Desktop/'
#your_path_here = '/Users/Christine/cs/'
os.chdir(your_path_here+'fraktur/segmentation')
os.chdir('/Users/Christine/cs/fraktur/segmentation')
main_dir = os.getcwd()
divorced = ['u', 'ů', 'ü', 'ù', 'û', 'n', 'm', 'w'] # letters than tend get divorced
blenders = ['e', 'è', 'é', 'ê', 'ë', 'r', 'v', 'ſ' ] # letters that tend blend into next
images1 = ['a.png', 'b.png', 'hi.png'] # testing images
images2 = ['hard.png', 'hard2.png', 'hoff.png']

# get correct labels from .txt transcription
def getLabels(filename):
    txt_file = filename[:-4]+'.txt' # get .txt filename
    ein = open(txt_file, 'r') # open .txt file
    raw = ein.read().rstrip() # read .txt file
    ein.close()
    txt = re.sub('[.,\'\"“„ ]', '', raw) # replace spaces and punctuation
    # add # chars for extra letters at the end from bad segmentation
    chars_str = txt+'{0:#^50}'.format('')
    chars_ls = [] # chars_str in list form, with digraphs and problem diacritics joined together
    i = 0
    while i < len(chars_str): # for each char in chars_str
        c = chars_str[i]
        if chars_str[i] == 'c' and chars_str[i+1] == 'h':
            chars_ls.append('ch') # treat 'ch' as one char
            i += 1
        elif chars_str[i] == 'ͤ': # treat this as diacritic, not separate letter
            chars_ls = chars_ls[:-1]
            chars_ls.append(chars_str[i-1]+chars_str[i])
        else: chars_ls.append(chars_str[i])
        i += 1
    return chars_ls # list of letter labels

# drip black pixels down or sideways to connect diacritics or gaps within a single letter
# takes binary inverted img, orig binary inverted img, contour dimensions, and drip direction
# returns new binary inverted img with drip added
# dir: 0 = drip down, 1 = drip right
# we need orig binary inverted img to find stop point without previous drips drawn on
def drip(bin, bin_orig, dims, dir):
    x, y, w, h = dims # dimensions of contour bounding box
    if dir == 0: # drip down
        xx = x+(w//2) # x center index (of contour)
        yy = y+(h//2) # y center index (of contour)
        # index of first 255 pixel going down from xx,yy, aka stopping point
        stop = y+h + np.where(bin_orig[:,xx-3][y+h+1:]==255)[0][0]
        # replace 0s in bin with 255s from contour center down to first 0
        # center adjusted by -3 because dots of i's are kinda skewed right usually
        bin[:,xx-3][yy:stop+1] = 255
    if dir == 1: # drip right
        xx = x+(w//2) # x center index (of contour)
        yy = y+(h//2) # y center index (of contour)
        # index of first 255 pixel going right from xx,yy, aka stopping point
        stop = x+w + np.where(bin_orig[yy][x+w+1:]==255)[0][0]
        # replace 0s in bin with 255s from contour center down to first 0
        bin[yy][xx:stop+1] = 255
    return bin # return new binary inverted img with drip added

# check for divorced u's, n's, m's, and w's
# take a single char img + label, return result
def sanityCheckDivorce(bin, bin_orig, dims, lab):
    x, y, w, h = dims # dimensions of contour bounding box
    ratioThresh = -1 # width/height ratio can't be less than this
    if lab in ['m', 'w']: ratioThresh = 1 # set ratioThresh
    else: ratioThresh = 0.7 # set ratioThresh for u's and n's
    ratio = w / h # width/height ratio of char image
    change = 0
    if ratio < ratioThresh: # if below ratioThresh, drip right
        bin = drip(bin, bin_orig, dims, 1)
        change = 1
    return (bin, change)

# check for e's, r's, v's, and ſ's blending into next letter
def sanityCheckBlend(bin, dims, lab):
    x, y, w, h = dims # dimensions of contour bounding box
    ratioThresh = 100 # width/height ratio can't be more than this
    if lab in ['e', 'r', 'ſ']: ratioThresh = 0.85
    if lab in ['v']: ratioThresh = 1
    ratio = w / h # width/height ratio of char image
    change = 0
    if ratio > ratioThresh: # if below ratioThresh, drip right
        change = 1
        temp = bin[y:y+h, x:x+w] # char matrix in bounding box
        mid = temp[:,(w//10):(w-w//10)] # cut of the left and right 10% of the char img
        blacks = [np.count_nonzero(x) for x in mid.T] # count black pixels per col
        # bin index of col in this char with fewest black pixels
        boundary_i = np.array(blacks).argmin() + w//10 + x
        bin[:,boundary_i] = 0
    return (bin, change)

# perform diacritic checks and sanity checks and morph img accordingly
# return new binary image
def morph(filename):
    labels = getLabels(filename) # get correct labels
    img, nimg, bin = preprocess(filename) # get img, flat img, and binary inverted img
    bin_orig = bin.copy()
    # find contour regions
    _, contours, _ = cv2.findContours(bin.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=lambda ctr: cv2.boundingRect(ctr)[0]) # sort contours in order
    ii = 0 # index of letter in labels
    i = 0 # index for contour regions
    next_letter = 1 # how much to increment index to next letter in txt labels
    divorce_flag = 0 # whether we're currently on a divorced letter
    diacritic_flag = 0
    blender_flag = 0
    while i < len(contours): # for each contour
        x, y, w, h = cv2.boundingRect(contours[i]) # get bounding box for cropping
        dims = [x, y, w, h] # dimensions of bounding box in list form
        ones = np.ones_like(nimg) # create array of 1s (almost blacks)
        mask = cv2.drawContours(ones, contours, i, 0, -1) # color contour area as 0
        # if 80% of region is white, don't count it (prob inside of 'e', 'd', etc.)
        if np.count_nonzero(bin[mask == 0]==0) / len(nimg[mask == 0]) > 0.75:
            i += 1 # move on to next contour
            continue
        # if it's really small, it's probably noise
        if h < len(nimg)/10 :
            i += 1 # move on to next contour
            continue
        lab = labels[ii] # get letter label for current contour
        ### DIACRITIC CHECK ###
        if h < len(nimg)/3: # if region really small, might be noise
            if y+h < len(nimg)/2: # but if it's in the top half, probably diacritic
                bin = drip(bin, bin_orig, dims, 0) # drip down to connect it to letter body
                lab = labels[ii-1] # use prev letter label, since diacritics usually after letter body
                diacritic_flag = 1 # stay on current letter which is actually the next one
            else: # if not in top half, it's not a diacritic, just noise
                i += 1 # move on to next contour
                continue
        ### SANITY CHECK for DIVORCEES ###
        elif lab in divorced: # check for commonly divorced letters
            if divorce_flag != 1: # =1 means connection already drawn from other half of divorced chunk
                bin, divorce_flag = sanityCheckDivorce(bin, bin_orig, dims, lab)
            else: divorce_flag = 0 # exit divorce_flag
        ### SANITY CHECK for BLENDING ###
        elif lab in blenders: # check for commonly blended letters
            bin, blender_flag = sanityCheckBlend(bin, dims, lab)
        # determine next_letter increment
        if diacritic_flag == 1: # if this contour was a diacritic mark,
            next_letter = 0 # we're already on the next letter, so stay on it
            diacritic_flag = 0 # reset diacritic_flag
        elif divorce_flag == 1: # if currently on divorced letter,
            next_letter = 0 # don't advance to next letter until divorce is settled
        elif blender_flag == 1:
            next_letter = 2
            blender_flag = 0
        else: next_letter = 1 # otherwise, go on to next letter label
        ii += next_letter
        i += 1 # move on to next contour
    # save resulting binary img after morphological operations
    cv2.imwrite(main_dir+'/letters/'+filename[:-4]+'_morph.png', bin)
    return (img, nimg, bin)

filename = 'hard.png'
# save image for each segmented char, and full image with char boundaries drawn on
def seg(filename, thck=2):
    labels = getLabels(filename) # get correct labels
    # orig img, flat img, and binary inverted img adjusted for diacritic and sanity checks
    img, nimg, bin = morph(filename)
    os.chdir(main_dir+'/letters') # dir to save cropped letter images
    _, contours, _ = cv2.findContours(bin.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE) # find contour regions
    contours = sorted(contours, key=lambda ctr: cv2.boundingRect(ctr)[0])
    ii = 0 # index of letter in txt
    for i in range(len(contours)): # for each contour region, save cropped img
        ones = np.ones_like(nimg) # create array of 1s (almost blacks)
        mask = cv2.drawContours(ones, contours, i, 0, -1) # color contour area as 0
        out = np.full_like(nimg, 255) # create array of 255s (whites)
        out[mask == 0] = nimg[mask == 0] # where mask is 0, change out value to img value
        x, y, w, h = cv2.boundingRect(contours[i]) # get bounding box for cropping
        roi = out[y:y+h, x:x+w] # getting roi (region of interest)
        if np.count_nonzero(bin[mask == 0]==0)/len(nimg[mask == 0]) > 0.75:
            continue # if 80% of region is white (0 = black, since bin is inverted)
        if len(roi) < len(nimg)/3: # if region really small, it's prob noise blob
            continue
        else: lab = labels[ii]
        cv2.imwrite('{}_{}_{}.png'.format(filename[:-4], i, lab), roi) # save cropped output image
        cv2.drawContours(img, contours, i, (0,0,255), thickness=thck) # draw boundary on full img
        ii += 1
    cv2.imwrite(filename, img) # save full image with regions drawn in red
    os.chdir(main_dir)

# execute
os.chdir(main_dir+'/test_data') # location of img
for img in images2:
    os.chdir(main_dir+'/test_data') # location of img
    seg(img, 2)
# seg('hard.png')
