# Letterboxd Unfollower

Letterboxd Unfollower contains a python program that allows the user to unfollow accounts on [Letterboxd](https://letterboxd.com/) This program takes influence from `@ShiloBuchnik`'s [Letterboxd Unfollower](https://github.com/ShiloBuchnik/letterboxd_unfollower/)

## The Searcher

The searcher is made up of the `follow_scraping` and `getUsers` functions which utilize Beautiful Soup to search through Letterboxd page HTML code in order to find accounts and their information. This search can take less time depending on what the user's filters require.

### Finding Accounts

The program finds accounts through the user's following list, which can show up to 255 pages with 25 accounts listed each. This is where the program finds its largest restrictions since Letteroxd only allows 25 accounts to load at a time and can only consider the user's most recent 6375 follows. Luckily, this process is extremely optimized in order to decrease search time.

### Finding Attributes

The program finds attributes of accounts that the user follows through both the user's following list as well as the account's likes webpage. While the usernames, following counts, follower counts, and following/follower ratios are all scraped from the following list, the review likes count is retrieved from the account's likes webpage. Since checking for review likes requires a separate webpage to be considered per account, this attribute is both considered last and includes a separate HTML check of an account's total likes from the following page to prevent unnecessary requests.

## The Unfollower

The unfollower is made up of the `unfollow` function, which has almost entirely been written by `@ShiloBuchnik` and most comments within the file are from them. The `unfollow` function takes in a list of account usernames that have been extracted from accounts found by the searcher. It then uses the Selenium library to interact with Chrome without a GUI or loading anything unnecessary, and unfollows the accounts discovered by the searcher.

### Verification

The unfollower is only activated if there have been accounts found that match the search and if the user inputs a correct password. The characters typed into the password are masked with the character `*` which is done by using the pwinput library.
