# haar cascade: for face detection
# lbph: local binary patterns histogram : for face recognition (creates a histogram for the subtraction)
# face_recognition uses hog (Histogram of Oriented Gradients)
# adaboost: boosting the haar cascade algorithm

from collections import Counter
import pandas as pd
import numpy as np
from mysql.connector import MySQLConnection
import face_recognition
import cv2
import os
from twilio.rest import Client
import pwinput

#fetch data from database
db = MySQLConnection(host='localhost', username='root',
                     password=os.environ['MYSQL_PASSWORD'], database='my_db')
cursor = db.cursor(buffered=True)
cursor.execute("SELECT * FROM isaa_users")
temp_users = cursor.fetchall()
cols = ["user_id", "name", "contact", "pin", "personal_limit"]
user = pd.DataFrame(temp_users, columns=cols)
bank_limit = 100000


# accessing the image folder
BASE_DIR = os.getcwd()
image_dir = os.path.join(BASE_DIR, "Images")

def get_encoded_faces():
    encoded = {}
    for dirpath, dnames, fnames in os.walk(image_dir):
        for f in fnames:
            if f.endswith(".jpg") or f.endswith(".png") or f.endswith(".jpeg") or f.endswith(".PNG") or f.endswith(".JPG") or f.endswith(".JPEG"):
                face = face_recognition.load_image_file("Images/" + f)
                # encoding for the first recognized face in the image
                encoding = face_recognition.face_encodings(face)[0]
                encoded[f.split(".")[0]] = encoding
    return encoded


def classify_face():
    # opens webcam (0 for our own webcam)
    video_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    faces = get_encoded_faces()  # dictionary
    known_face_encodings = list(faces.values())
    known_face_names = list(faces.keys())
    face_locations = []
    face_encodings = []
    face_names = []
    process_this_frame = True
    while True:
        # frame is the image from the webcam
        ret, frame = video_capture.read()
        # resizing the image to 1/4 its size
        small_frame = cv2.resize(
            frame, (0, 0), None, 0.25, 0.25)  # type: ignore
        rgb_small_frame = small_frame[:, :, ::-1]
        # faces from the webcam
        # bounding box for the face (gives a tuple of four values - top/bottom/right/left)
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        for encodeFace, faceLoc in zip(face_encodings, face_locations):
            # compare_faces returns boolean values based on the tolerance (0.5 here) 
            matches = face_recognition.compare_faces(
                known_face_encodings, encodeFace, 0.5)
            # a numpy array of distances
            faceDis = face_recognition.face_distance(
                known_face_encodings, encodeFace)
            # finding the closest match (obtained from the minimum distance)
            matchIndex = np.argmin(faceDis)
            name = "Unknown"

            if matches[matchIndex]:
                name = known_face_names[matchIndex]
                y1, x2, y2, x1 = faceLoc
                # reseize the locations of the face
                y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
                # to create the named bounding boxes in the video stream from the webcam
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(frame, (x1, y2-35), (x2, y2),
                              (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (x1-6, y2-6),
                            cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 2)

            # if no match then shows unknown
            if not matches[matchIndex]:
                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(frame, (x1, y2-35), (x2, y2),
                              (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (x1-6, y2-6),
                            cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 2)

            face_names.append(name)
        # close the video stream and turn the webcam off
        cv2.imshow("Video", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if len(face_names) == 20:
            break

    video_capture.release()
    cv2.destroyAllWindows()
    return face_names

print()
name = input("Enter your Name: ").upper()
correct_password = user[user['name'] == name]['pin'].iloc[0]
for i in [1, 2, 3]:
    pwd = int(pwinput.pwinput(prompt = "Enter your 4-digit pin: "))
    if pwd == correct_password:
        print("Access Granted!")
        break
    elif i == 3 and pwd != correct_password:
        print("Wrong Pin! Access Denied!")
        exit()
    else:
        print("Wrong Pin! {} more tries left!".format(3-i))
        continue

print()
amnt = int(input("Enter your withdrawal amount: "))
p_limit = int(user[user['name'] == name]['personal_limit'].iloc[0])
if amnt > bank_limit:
    print("Amount Exceeds Bank Limit! Access Denied!")
    exit()
if amnt < p_limit:
    print("Transaction Successful!")
    exit()
else:
    print("Amount exceed Personal Limit!\n---Complete Face Verification----")
faceID = Counter(classify_face()).most_common(1)[0][0]
print()
print("User Identified: ", faceID)
if name == faceID:
    print("Face ID matches User name!")
    print("---Complete OTP verification---")
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    verify_sid = os.environ['VERIFY_SID']
    client = Client(account_sid, auth_token)
    
    verification = client.verify.services(verify_sid)
    print()
    for i in [1, 2, 3]:
        #send message
        ph_num = '+91' + user[user['name'] == name]['contact'].iloc[0]
        verification.verifications.create(to=ph_num, channel='sms')
        #take otp from user
        otp_code = input("Please enter the OTP:")
        #check otp with 3rd party
        verification_check = verification.verification_checks.create(to=ph_num, code=otp_code)
        if verification_check.status=='approved':
            print("Access Granted!")
            print("Transaction Successful!")
            exit()
        elif i == 3 and verification_check.status!='approved':
            print("Wrong OTP! Access Denied!")
            print("Cancelling Transaction")
            exit()
        else:
            print(f"Wrong OTP! {3-i} more tries left!")
            continue
else:
    print("\nAccess Denied!")
