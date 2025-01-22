import pwinput
from bs4 import BeautifulSoup
from colorama import Fore, Style
from enum import Enum, auto
import getpass
import re
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import time


class Account:
	def __init__(self, name, followers=None, following=None, ratio=None, review_likes=None):
		self.name = name
		self.followers = followers
		self.following = following
		self.review_likes = review_likes

	def __str__(self):
		return self.name

# Using an enum makes is a simple and effective way to keep track of the filters assigned by the user
class Filters(Enum):
	EXCLUDE = auto()
	FOLLOWING = auto()
	FOLLOWERS = auto()
	RATIO = auto()
	LIKES = auto()
	EXCEPT = auto()

	# An update function makes the code appear smoother
	def update(self, new_value):
		self._value_ = new_value


# Requests a username from the user and continues to until a valid one is entered
def getUsername(session):
	while True:
		user = input(Fore.GREEN + "Please enter your username: " + Fore.RESET)
		url = f"https://letterboxd.com/{user}/"
		user_html = session.get(url)
		soup = BeautifulSoup(user_html.text, 'html.parser') # Allows for easy lookup of html needed to complete our searches
		if soup.find(string="Sorry, we can’t find the page you’ve requested."):  # Ensures the username exists
			input(Fore.RED + "That user does not exist, please try again." + Fore.RESET)
		else:
			return user



def getUsers(session, url):
	i = 1
	followers = set()
	if Filters.EXCLUDE.value == 'y': # We only need to find all of the followers of the user's account if the accounts to be unfollowed can't follow them back
		while True:
			follower_html = session.get(f"{url}followers/page/{i}")
			soup = BeautifulSoup(follower_html.text, 'html.parser') # BeautifulSoup once again makes things easy

			curr_page_names = soup.find_all('a', class_='name') # This finds all account elements on the user's page
			if not curr_page_names: # If there are not any account elements found, we have reached the end of the follower list or past the 255th page
				break

			for n in curr_page_names: # Extracts all usernames from the elements collected
				temp = n.get("href").lower()
				followers.add(temp[1:-1])

			i += 1

	following = []
	follower_counts = [] # Keeps track of follower counts
	following_counts = [] # Keeps track of following counts
	like_counts = [] # Keeps track of TOTAL like counts

	return_list = [] # The list which will contain all of the accounts to be unfollowed

	i = 1
	while True:
		follower_html = session.get(f"{url}following/page/{i}")
		soup = BeautifulSoup(follower_html.text, 'html.parser')

		curr_page_names = soup.find_all('a', class_='name') # Just like with the followers, this finds all account elements
		if not curr_page_names: # Stops checking pages if there are no more accounts listed
			break

		for n in curr_page_names: # Extracts all the usernames from the html elements
			temp = n.get("href").lower()
			following.append(temp[1:-1])

		# Follower and following counts only matter in cases where ratio or follow counts are being considered
		if Filters.RATIO.value != "" or Filters.FOLLOWING.value != "" or Filters.FOLLOWERS.value != "":
			curr_page_follow_stats = soup.find_all('a', class_='_nobr') # Finds all following and followers counts
			for count in range(0, len(curr_page_follow_stats), 2): # A follower count never appears without a corresponding following count and vise-versa
				text = curr_page_follow_stats[count].get_text()
				follower_counts.append(re.sub(r'[^0-9]', '', text)) # Cuts down the text from the element to only the numbers
				text = curr_page_follow_stats[count + 1].get_text()
				following_counts.append(re.sub(r'[^0-9]', '', text))

		if Filters.LIKES.value != "": # Needed to minimize extra requests later
			curr_page_like_stats = soup.find_all("a", class_="has-icon icon-16 icon-liked")
			for element in curr_page_like_stats:
				text = element.get_text(strip=True)
				like_counts.append(re.sub(r'[^0-9]', '', text))


		i += 1


	for account in range(len(following)): # Iterates through all possible accounts the user follows
		def apply_filter(filter_value, actual_value): # A math-based function to figure out if an account's statistic matches the filters specified
			sign = -1 if filter_value[0] == '>' else 1
			diff = sign * (float(filter_value[1:]) - actual_value)
			return diff > 0

		acc = Account(following[account]) # Creates an account object to modify

		if (Filters.EXCLUDE.value == 'y' and acc.name in followers) or (acc.name in Filters.EXCEPT.value):
			continue # Continuing stops this account from being considered any further

		if Filters.FOLLOWING.value != "": # Checks if following count matters
			acc.following = int(following_counts[account])
			if not apply_filter(Filters.FOLLOWING.value, acc.following):
				continue

		if Filters.FOLLOWERS.value != "": # Checks if follower counts matter
			acc.followers = int(follower_counts[account])
			if not apply_filter(Filters.FOLLOWERS.value, acc.followers):
				continue

		if Filters.RATIO.value != "": # Checks if ratio matters
			acc.following = int(following_counts[account])
			acc.followers = int(follower_counts[account])
			acc.ratio = acc.following / acc.followers
			match = re.match(r"([><])(\d+)/(\d+)", Filters.RATIO.value)
			filter_ratio = match.group(1) + str(float(match.group(2)) / float(match.group(3)))
			if not apply_filter(filter_ratio, acc.ratio):
				continue

		if Filters.LIKES.value != "": # Check if review likes matter
			if not apply_filter(Filters.LIKES.value, int(like_counts[account])):
				continue
			likes_html = session.get(f"https://letterboxd.com/{acc.name}/likes/films/") # We must open a new page to check an account's liked reviews
			soup = BeautifulSoup(likes_html.text, 'html.parser')
			likes = soup.find('a', string=" Reviews ")
			if not likes:
				continue # Conservatively does not consider an account should Letterboxd not load properly
			elif likes.get("title"): # If this value is not None, the like count is not zero
				acc.review_likes = int(re.sub(r'[^0-9]', '', likes.get("title")))
			else: # If `likes.get("title")` returns None, the like count is zero
				acc.review_likes = 0
			if not apply_filter(Filters.LIKES.value, acc.review_likes):
				continue

		return_list.append(acc) # The account is only added to the list if it matches all filters

	return return_list


def follow_scraping(session, username): # Collects all of the accounts to be unfollowed

	url = f"https://letterboxd.com/{username}/"

	unfollow_list = getUsers(session, url)

	return unfollow_list


def check(): # Collects inputs by asking about each filter

	class Question: # This allows questions to be asked simply and consistently, as well as allowing for new questions to be added easily
		def __init__(self, value=None, pattern=None, default="", text=""):
			self.value = value
			self.pattern = pattern
			self.default = default
			self.text = text

	character = input("\nAccount found. Would you like to proceed to unfollow specific accounts? [Y/N]\n")
	while character.lower() != 'y' and character.lower() != 'n':
		character = input(Fore.RED + "Invalid input, please try again: " + Fore.RESET)

	if character.lower() == 'y': # Program terminates should 'n' be entered

		# This is the list of all of the questions that will collect the desired filters from the user
		questions = [
			Question(value=Filters.EXCLUDE, pattern=r"^[yn]$", default="y",
					 text="Do these accounts have to not follow you back? [Y/N]\n"),
			Question(value=Filters.FOLLOWING, pattern=r"^[><]\d+$",
					 text="Please enter the minimum [>] or maximum [<] amount of following accounts to be unfollowed should have.\n[e.g. <5000]: "),
			Question(value=Filters.FOLLOWERS, pattern=r"^[><]\d+$",
					 text="Please enter the minimum [>] or maximum [<] amount of followers accounts to be unfollowed should have.\n[e.g. >3500]: "),
			Question(value=Filters.RATIO, pattern=r"^[><]\d+/\d+$",
					 text="Please enter the minimum [>] or maximum [<] following/follower ratio of accounts to be unfollowed?\n[e.g. >3/2]: "),
			Question(value=Filters.LIKES, pattern=r"^[><]\d+$",
					 text="Please enter the minimum [>] or maximum [<] amount of review likes accounts to be unfollowed should have.\n[e.g. >1000]: "),
			Question(value=Filters.EXCEPT, pattern=r"[\s\S]*", default=[],
					 text="Please enter any usernames of accounts that you would like to be excluded from this search.\n[e.g. Scorsese,GERWIG,NoLaN]: ")
		]

		print(Fore.MAGENTA + "\nPlease respond to the following questions in their specified format. (If you would like a certain field to not be considered, leave it blank." + Fore.RESET)

		for question in questions: # Asks each question
			response = input(Fore.BLUE + question.text + Fore.RESET).lower()
			while not re.match(question.pattern, response) and response.lower() != "": # Ensures that each response matches the required format
				response = input(Fore.RED + "Invalid format, please try again:\n" + Fore.RESET)
			if response == "": # Blank responses mean a field should not be considered
				response = question.default
			elif question.value is Filters.EXCEPT: # The "except" filter is the only one that requires a list and is therefore treated differently
				no_spaces = re.sub(r"\s+", "", response)
				response = no_spaces.split(',')
			question.value.update(response) # Updates the Filters enum

		return True

	return False


def unfollow(username, password, unfollow_list):
	options = Options() # Allows for browser setting configuration for Chrome Webdriver
	# Removes unnecessary logging which decreases time needed
	options.add_experimental_option('excludeSwitches', ['enable-logging'])
	# Disables loading images, to make the program run faster.
	options.add_argument('--blink-settings=imagesEnabled=false')
	# Headless browsing allows chrome to be run without a visible GUI.
	options.add_argument("--headless=new")
	# Improves performance since the GPU is unneeded in this instance
	options.add_argument("--disable-gpu")
	# By default, the page load strategy is set to 'normal',
	# which means the WebDriver waits until the entire page loads (HTML file and sub-resources are downloaded).
	# We set it to 'eager', in which the WebDriver waits only until the element itself appears (HTML file is downloaded only).
	# It makes a BIG difference in performance. Before this addition, the program would get stuck a lot, by waiting for the entire page.
	options.page_load_strategy = 'eager'

	driver = webdriver.Chrome(options=options)
	# Using EC (wait until...) over sleep() makes the code much more efficient. We set the timeout limit to 10.
	wait = WebDriverWait(driver, 10)
	driver.get("https://letterboxd.com/sign-in")

	# Logging in
	username_field = wait.until(EC.element_to_be_clickable((By.ID, "field-username")))
	password_field = wait.until(EC.element_to_be_clickable((By.ID, "field-password")))
	username_field.send_keys(username)
	password_field.send_keys(password)
	password_field.send_keys(Keys.RETURN) # Submitting the input fields by pressing 'Enter' on the password field

	try:
		# Makes us wait for the login to complete (this arbitrary element is visible only after a successful login)
		# We use 'presence' and not 'visibility' because we only care if the element is present on the DOM.
		# This makes things a *bit* faster
		wait.until(EC.presence_of_element_located((By.ID, "add-new-button")))
	except TimeoutException:
		print(Fore.RED + "Wrong username or password, terminating..." + Fore.RESET)
		driver.quit()
		return

	# In this loop we unfollow every username
	for username in unfollow_list:
		driver.get(f"https://letterboxd.com/{username}")
		button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.js-button-following")))
		button.click()
		# Without 'sleep', sometimes the driver won't be able to find the button for some reason
		time.sleep(0.5)

	driver.quit() # Close the driver instance completely. The program ends right after, but to be on the safe side...
	print(Fore.GREEN + "Unfollowing successful!" + Fore.RESET)


def main():

	session = requests.Session() # Opening a session saves a lot of time since we can expect to make many requests
	username = getUsername(session) # Retrieves the username of the account we will use from the user

	if check(): # The check function is what asks for all the filters from the user
		print(Fore.RED + "Finding corresponding accounts, please wait..." + Fore.RESET)
		unfollow_list = follow_scraping(session, username) # Finds all accounts that match the description given by the user
		unfollow_names = [acc.name for acc in unfollow_list] # Creates a list of all of the usernames of the accounts to be unfollowed

		if unfollow_names: # The program will terminate should no accounts match the desired description
			response = input(f"\nThe following accounts match that description: {Fore.GREEN}{", ".join(unfollow_names)}\n{Fore.RESET}Proceed to unfollow? [Y/N]: ")
			while not re.match(r"^[YyNn]$", response): # Ensures the input is boolean
				response = input(Fore.RED + "Invalid format, please try again:\n" + Fore.RESET)
			if response.lower() == 'y': # If the user continues, they are prompted with a password request, masked using pwinput
				password = pwinput.pwinput(prompt=(Fore.GREEN + "Please enter your password: " + Fore.RESET), mask='*')
				unfollow(username, password, unfollow_names) # Unfollows all accounts matching the desired description
		else:
			print(Fore.RED + "No accounts match that description." + Fore.RESET)
			time.sleep(1)

	print(Fore.RED + "Terminating..." + Fore.RESET)
	time.sleep(2)


if __name__ == '__main__':
	main()
