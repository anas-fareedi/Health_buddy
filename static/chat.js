$(document).ready(function() {
	// Auto scroll to bottom
	function scrollToBottom() {
		var messageBody = document.getElementById('messageFormeight');
		messageBody.scrollTop = messageBody.scrollHeight;
	}
	$("#messageArea").on("submit", function(event) {
		event.preventDefault();
		
		const date = new Date();
		const hour = date.getHours();
		const minute = date.getMinutes().toString().padStart(2, '0');
		const str_time = hour+":"+minute;
		var rawText = $("#text").val().trim();
		
		if (!rawText) {
			return;
		}
		
		var userMessageElement = $('<div class="msg_cotainer_send">').text(rawText);
		userMessageElement.append($('<span class="msg_time_send">').text(str_time));
		var userHtml = $('<div class="d-flex justify-content-end mb-4">')
			.append(userMessageElement)
			.append('<div class="img_cont_msg"><img src="https://i.ibb.co/d5b84Xw/Untitled-design.png" class="rounded-circle user_img_msg"></div>');
		
		$("#text").val("");
		$("#messageFormeight").append(userHtml);
		scrollToBottom();
		
		// Show loading indicator
		var loadingMessageElement = $('<div class="msg_cotainer">').text("Thinking...");
		loadingMessageElement.append($('<span class="msg_time">').text(str_time));
		var loadingHtml = $('<div class="d-flex justify-content-start mb-4" id="loading">')
			.append('<div class="img_cont_msg"><img src="https://cdn-icons-png.flaticon.com/512/387/387569.png" class="rounded-circle user_img_msg"></div>')
			.append(loadingMessageElement);
		$("#messageFormeight").append(loadingHtml);
		scrollToBottom();
		
		// Disable send button
		$("#send").prop('disabled', true);

		$.ajax({
			data: {
				msg: rawText,	
			},
			type: "POST",
			url: "/get",
		}).done(function(data) {
			// Remove loading indicator
			$("#loading").remove();
			
			var answerText = data.answer || "No response received.";
			var botMessageElement = $('<div class="msg_cotainer">').text(answerText);
			botMessageElement.append($('<span class="msg_time">').text(str_time));
			var botHtml = $('<div class="d-flex justify-content-start mb-4">')
				.append('<div class="img_cont_msg"><img src="https://cdn-icons-png.flaticon.com/512/387/387569.png" class="rounded-circle user_img_msg"></div>')
				.append(botMessageElement);
			$("#messageFormeight").append(botHtml);
			scrollToBottom();
			
			// Enable send button
			$("#send").prop('disabled', false);
		}).fail(function(xhr, status, error) {
			// Remove loading indicator
			$("#loading").remove();
			
			var errorMessageElement = $('<div class="msg_cotainer">').text("Sorry, I encountered an error. Please try again.");
			errorMessageElement.append($('<span class="msg_time">').text(str_time));
			var errorHtml = $('<div class="d-flex justify-content-start mb-4">')
				.append('<div class="img_cont_msg"><img src="https://cdn-icons-png.flaticon.com/512/387/387569.png" class="rounded-circle user_img_msg"></div>')
				.append(errorMessageElement);
			$("#messageFormeight").append(errorHtml);
			scrollToBottom();
			
			// Enable send button
			$("#send").prop('disabled', false);
		});
	});
});
