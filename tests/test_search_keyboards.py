"""Tests for search keyboard utilities."""

import pytest
from aiogram .types import InlineKeyboardMarkup ,InlineKeyboardButton

from src .bot .keyboards .search_keyboards import SearchKeyboards

class TestSearchKeyboards :
    """Test search keyboard utilities."""

    def test_create_search_results_keyboard (self ):
        """Test creating search results keyboard."""
        items =[
        {
        'id':1 ,
        'title':'Nike Sneakers',
        'price':25.99 ,
        'currency':'EUR',
        'brand':'Nike'
        },
        {
        'id':2 ,
        'title':'Vintage Jacket',
        'price':45.50 ,
        'currency':'EUR',
        'brand':'Adidas'
        }
        ]

        keyboard =SearchKeyboards .create_search_results_keyboard (items ,page =1 )

        assert isinstance (keyboard ,InlineKeyboardMarkup )

        assert len (keyboard .inline_keyboard )>=2

        first_button =keyboard .inline_keyboard [0 ][0 ]
        assert "1. Nike Sneakers"in first_button .text
        assert first_button .callback_data =="item_detail:1"

        second_button =keyboard .inline_keyboard [1 ][0 ]
        assert "2. Vintage Jacket"in second_button .text
        assert second_button .callback_data =="item_detail:2"

        nav_row =keyboard .inline_keyboard [-1 ]
        new_search_button =None
        for button in nav_row :
            if "New Search"in button .text :
                new_search_button =button
                break

        assert new_search_button is not None
        assert new_search_button .callback_data =="new_search"

    def test_create_search_results_keyboard_with_pagination (self ):
        """Test creating search results keyboard with pagination."""
        items =[{'id':i ,'title':f'Item {i }','price':10.0 ,'currency':'EUR'}
        for i in range (15 )]

        keyboard =SearchKeyboards .create_search_results_keyboard (items ,page =2 )

        nav_row =keyboard .inline_keyboard [-1 ]

        prev_button =None
        next_button =None
        for button in nav_row :
            if "Previous"in button .text :
                prev_button =button
            elif "Next"in button .text :
                next_button =button

        assert prev_button is not None
        assert prev_button .callback_data =="search_page:1"

        assert next_button is not None
        assert next_button .callback_data =="search_page:3"

    def test_create_search_results_keyboard_long_title (self ):
        """Test creating keyboard with long item titles."""
        items =[
        {
        'id':1 ,
        'title':'This is a very long item title that should be truncated',
        'price':25.99 ,
        'currency':'EUR'
        }
        ]

        keyboard =SearchKeyboards .create_search_results_keyboard (items )

        first_button =keyboard .inline_keyboard [0 ][0 ]
        assert "..."in first_button .text
        assert len (first_button .text )<=50

    def test_create_item_detail_keyboard (self ):
        """Test creating item detail keyboard."""
        item ={
        'id':123 ,
        'title':'Test Item',
        'url':'https://vinted.at/items/123',
        'photos':[
        {'url':'photo1.jpg','order_no':0 },
        {'url':'photo2.jpg','order_no':1 }
        ]
        }

        keyboard =SearchKeyboards .create_item_detail_keyboard (item )

        assert isinstance (keyboard ,InlineKeyboardMarkup )

        vinted_button =keyboard .inline_keyboard [0 ][0 ]
        assert "View on Vinted"in vinted_button .text
        assert vinted_button .url ==item ['url']

        photos_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "View Photos"in button .text :
                    photos_button =button
                    break

        assert photos_button is not None
        assert "2"in photos_button .text
        assert photos_button .callback_data =="item_photos:123:0"

        back_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "Back to Results"in button .text :
                    back_button =button
                    break

        assert back_button is not None
        assert back_button .callback_data =="back_to_results"

        new_search_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "New Search"in button .text :
                    new_search_button =button
                    break

        assert new_search_button is not None
        assert new_search_button .callback_data =="new_search"

    def test_create_item_detail_keyboard_single_photo (self ):
        """Test creating item detail keyboard with single photo."""
        item ={
        'id':123 ,
        'title':'Test Item',
        'url':'https://vinted.at/items/123',
        'photos':[{'url':'photo1.jpg','order_no':0 }]
        }

        keyboard =SearchKeyboards .create_item_detail_keyboard (item )

        photos_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "View Photos"in button .text :
                    photos_button =button
                    break

        assert photos_button is None

    def test_create_item_detail_keyboard_no_photos (self ):
        """Test creating item detail keyboard with no photos."""
        item ={
        'id':123 ,
        'title':'Test Item',
        'url':'https://vinted.at/items/123',
        'photos':[]
        }

        keyboard =SearchKeyboards .create_item_detail_keyboard (item )

        photos_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "View Photos"in button .text :
                    photos_button =button
                    break

        assert photos_button is None

    def test_create_photo_navigation_keyboard (self ):
        """Test creating photo navigation keyboard."""
        keyboard =SearchKeyboards .create_photo_navigation_keyboard (
        item_id =123 ,
        current_photo =1 ,
        total_photos =3
        )

        assert isinstance (keyboard ,InlineKeyboardMarkup )

        counter_button =keyboard .inline_keyboard [0 ][0 ]
        assert "2 / 3"in counter_button .text
        assert counter_button .callback_data =="noop"

        nav_row =keyboard .inline_keyboard [1 ]
        assert len (nav_row )==2

        prev_button =nav_row [0 ]
        assert "Previous"in prev_button .text
        assert prev_button .callback_data =="item_photos:123:0"

        next_button =nav_row [1 ]
        assert "Next"in next_button .text
        assert next_button .callback_data =="item_photos:123:2"

        back_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "Back to Item"in button .text :
                    back_button =button
                    break

        assert back_button is not None
        assert back_button .callback_data =="item_detail:123"

        vinted_button =None
        for row in keyboard .inline_keyboard :
            for button in row :
                if "View on Vinted"in button .text :
                    vinted_button =button
                    break

        assert vinted_button is not None
        assert vinted_button .url =="https://www.vinted.at/items/123"

    def test_create_photo_navigation_keyboard_first_photo (self ):
        """Test photo navigation keyboard for first photo."""
        keyboard =SearchKeyboards .create_photo_navigation_keyboard (
        item_id =123 ,
        current_photo =0 ,
        total_photos =3
        )

        counter_button =keyboard .inline_keyboard [0 ][0 ]
        assert "1 / 3"in counter_button .text

        nav_row =keyboard .inline_keyboard [1 ]
        assert len (nav_row )==1

        next_button =nav_row [0 ]
        assert "Next"in next_button .text
        assert next_button .callback_data =="item_photos:123:1"

    def test_create_photo_navigation_keyboard_last_photo (self ):
        """Test photo navigation keyboard for last photo."""
        keyboard =SearchKeyboards .create_photo_navigation_keyboard (
        item_id =123 ,
        current_photo =2 ,
        total_photos =3
        )

        counter_button =keyboard .inline_keyboard [0 ][0 ]
        assert "3 / 3"in counter_button .text

        nav_row =keyboard .inline_keyboard [1 ]
        assert len (nav_row )==1

        prev_button =nav_row [0 ]
        assert "Previous"in prev_button .text
        assert prev_button .callback_data =="item_photos:123:1"

    def test_create_error_keyboard (self ):
        """Test creating error keyboard."""
        keyboard =SearchKeyboards .create_error_keyboard ()

        assert isinstance (keyboard ,InlineKeyboardMarkup )

        button =keyboard .inline_keyboard [0 ][0 ]
        assert "Try New Search"in button .text
        assert button .callback_data =="new_search"

    def test_create_premium_required_keyboard (self ):
        """Test creating premium required keyboard."""
        keyboard =SearchKeyboards .create_premium_required_keyboard ()

        assert isinstance (keyboard ,InlineKeyboardMarkup )

        upgrade_button =keyboard .inline_keyboard [0 ][0 ]
        assert "Upgrade to Premium"in upgrade_button .text
        assert upgrade_button .callback_data =="upgrade_premium"

        referral_button =keyboard .inline_keyboard [1 ][0 ]
        assert "Get Referral Link"in referral_button .text
        assert referral_button .callback_data =="get_referral"