# from PIL import Image
import easyocr


# def extract_text_tesseract(img_filename):
#     # clean_img(photo_name)
#     # return pytesseract.image_to_string(Image.open(BytesIO(img_content)))
#     return pytesseract.image_to_string(Image.open(img_filename))

def extract_text_easyocr(img_filename):
    reader = easyocr.Reader(['en'])
    results = reader.readtext(img_filename)
    recognised_text = []
    for bbox, text, prob in results:
        recognised_text.append(text)
    return recognised_text


# clean_img('chonky.jpg')

# import requests, time, datetime
# response = requests.get('https://pbs.twimg.com/media/GtpzJBXaQAAGcm0?format=jpg&name=small')
# with open('test_img.jpeg', 'wb') as f:
#     f.write(response.content)


# result = exctract_text_easyocr2('test_img.jpeg')
# print(result)
# result = exctract_text_tes(response.content)
#
# before = time.time()
# result = exctract_text_easyocr(response.content)
# result = extract_text_tesseract(response.content)
# print(result)
# after = time.time()
# print(after-before)
# print(f'time before: {datetime.datetime.fromtimestamp(before)}')
# print(f'time after: {datetime.datetime.fromtimestamp(after)}')
