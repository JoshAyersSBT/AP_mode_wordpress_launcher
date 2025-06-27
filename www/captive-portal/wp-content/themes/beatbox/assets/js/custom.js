(function ($) {
$('.toggler').on('click', function () {
    $('.sidenav-header, .list-item').toggleClass('collapsed');
	$('.custom-sticky-wrapper').toggleClass('expended');

    // Store collapsed state
    let isCollapsed = $('.sidenav-header').hasClass('collapsed');
    localStorage.setItem('sidebarCollapsed', isCollapsed ? 'true' : 'false');
});

// Apply stored state on page load
$(document).ready(function () {
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        $('.sidenav-header, .list-item').addClass('collapsed');
        $('.custom-sticky-wrapper').addClass('expended');
    }
});
})(jQuery);