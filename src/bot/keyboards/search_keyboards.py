"""Search-related keyboard utilities."""

from typing import List ,Dict ,Any
from aiogram .types import InlineKeyboardMarkup ,InlineKeyboardButton
from aiogram .utils .keyboard import InlineKeyboardBuilder

class SearchKeyboards :
    """Utility class for creating search-related keyboards."""

    @staticmethod
    def create_search_results_keyboard (items :List [Dict [str ,Any ]],page :int =1 )->InlineKeyboardMarkup :
        """
        Create inline keyboard for search results.

        Args:
            items: List of item dictionaries
            page: Current page number

        Returns:
            InlineKeyboardMarkup with item buttons
        """
        builder =InlineKeyboardBuilder ()

        for i ,item in enumerate (items [:10 ]):

            brand_text =f" • {item ['brand']}"if item .get ('brand')else ""
            price_text =f"{item ['price']:.2f} {item .get ('currency','EUR')}"
            button_text =f"{price_text }{brand_text }"

            title =item ['title']
            if len (title )>30 :
                title =title [:27 ]+"..."

            builder .button (
            text =f"{i +1 }. {title }",
            callback_data =f"item_detail:{item ['id']}"
            )

        builder .adjust (1 )

        nav_buttons =[]
        if page >1 :
            nav_buttons .append (
            InlineKeyboardButton (
            text ="◀️ Previous",
            callback_data =f"search_page:{page -1 }"
            )
            )

        nav_buttons .append (
        InlineKeyboardButton (
        text ="🔍 New Search",
        callback_data ="new_search"
        )
        )

        if len (items )>=10 :
            nav_buttons .append (
            InlineKeyboardButton (
            text ="Next ▶️",
            callback_data =f"search_page:{page +1 }"
            )
            )

        if nav_buttons :
            builder .row (*nav_buttons )

        return builder .as_markup ()

    @staticmethod
    def create_item_detail_keyboard (item :Dict [str ,Any ],show_photos :bool =False )->InlineKeyboardMarkup :
        """
        Create inline keyboard for item detail view.

        Args:
            item: Item dictionary
            show_photos: Whether to show photo navigation buttons

        Returns:
            InlineKeyboardMarkup with detail action buttons
        """
        builder =InlineKeyboardBuilder ()

        builder .button (
        text ="🔗 View on Vinted",
        url =item ['url']
        )

        photos =item .get ('photos',[])
        if len (photos )>1 :
            if not show_photos :
                builder .button (
                text =f"📸 View Photos ({len (photos )})",
                callback_data =f"item_photos:{item ['id']}:0"
                )
            else :

                builder .row (
                InlineKeyboardButton (
                text ="◀️ Prev Photo",
                callback_data =f"item_photos:{item ['id']}:prev"
                ),
                InlineKeyboardButton (
                text ="Next Photo ▶️",
                callback_data =f"item_photos:{item ['id']}:next"
                )
                )

        builder .button (
        text ="◀️ Back to Results",
        callback_data ="back_to_results"
        )

        builder .button (
        text ="🔍 New Search",
        callback_data ="new_search"
        )

        if len (photos )>1 and show_photos :
            builder .adjust (1 ,2 ,1 ,1 )
        else :
            builder .adjust (1 ,1 ,1 ,1 )

        return builder .as_markup ()

    @staticmethod
    def create_photo_navigation_keyboard (
    item_id :int ,
    current_photo :int ,
    total_photos :int
    )->InlineKeyboardMarkup :
        """
        Create keyboard for photo navigation.

        Args:
            item_id: Item ID
            current_photo: Current photo index (0-based)
            total_photos: Total number of photos

        Returns:
            InlineKeyboardMarkup with photo navigation
        """
        builder =InlineKeyboardBuilder ()

        builder .button (
        text =f"📸 {current_photo +1 } / {total_photos }",
        callback_data ="noop"
        )

        nav_buttons =[]

        if current_photo >0 :
            nav_buttons .append (
            InlineKeyboardButton (
            text ="◀️ Previous",
            callback_data =f"item_photos:{item_id }:{current_photo -1 }"
            )
            )

        if current_photo <total_photos -1 :
            nav_buttons .append (
            InlineKeyboardButton (
            text ="Next ▶️",
            callback_data =f"item_photos:{item_id }:{current_photo +1 }"
            )
            )

        if nav_buttons :
            builder .row (*nav_buttons )

        builder .button (
        text ="◀️ Back to Item",
        callback_data =f"item_detail:{item_id }"
        )

        builder .button (
        text ="🔗 View on Vinted",
        url =f"https://www.vinted.at/items/{item_id }"
        )

        builder .adjust (1 ,len (nav_buttons )if nav_buttons else 0 ,1 ,1 )

        return builder .as_markup ()

    @staticmethod
    def item_count_keyboard()->InlineKeyboardMarkup:
        """
        Create keyboard for item count selection.

        Returns:
            InlineKeyboardMarkup with item count options
        """
        builder = InlineKeyboardBuilder()

        # Common item count options
        counts = [5, 10, 20, 50, 100]

        for count in counts:
            builder.button(
                text=f"{count} товаров",
                callback_data=f"item_count:{count}"
            )

        # Custom option
        builder.button(
            text="✏️ Своё количество",
            callback_data="item_count:custom"
        )

        builder.adjust(2, 2, 1, 1)  # 2 buttons per row, then 2, then 1, then 1

        return builder.as_markup()

    @staticmethod
    def create_error_keyboard ()->InlineKeyboardMarkup :
        """
        Create keyboard for error messages.

        Returns:
            InlineKeyboardMarkup with retry option
        """
        builder =InlineKeyboardBuilder ()

        builder .button (
        text ="🔍 Try New Search",
        callback_data ="new_search"
        )

        return builder .as_markup ()

    @staticmethod
    def create_premium_required_keyboard ()->InlineKeyboardMarkup :
        """
        Create keyboard for premium required message.

        Returns:
            InlineKeyboardMarkup with upgrade and referral options
        """
        builder =InlineKeyboardBuilder ()

        builder .button (
        text ="💎 Upgrade to Premium",
        callback_data ="upgrade_premium"
        )

        builder .button (
        text ="👥 Get Referral Link",
        callback_data ="get_referral"
        )

        builder .adjust (1 )

        return builder .as_markup ()
