$(document).ready(function () {
	// ── Helpers ──────────────────────────────────────────────────
	function scrollToBottom() {
		var messageBody = document.getElementById("messageFormeight");
		messageBody.scrollTop = messageBody.scrollHeight;
	}

	function getTimeString() {
		var d = new Date();
		return d.getHours() + ":" + d.getMinutes().toString().padStart(2, "0");
	}

	// Build a bot-side message row (returns the inner .msg_cotainer element)
	function createBotBubble(time) {
		var container = $('<div class="msg_cotainer">');
		container.append($('<span class="msg_time">').text(time));
		var row = $('<div class="d-flex justify-content-start mb-4">')
			.append(
				'<div class="img_cont_msg"><img src="https://cdn-icons-png.flaticon.com/512/387/387569.png" class="rounded-circle user_img_msg"></div>'
			)
			.append(container);
		$("#messageFormeight").append(row);
		return container;
	}

	// ── Upload Toast helpers ────────────────────────────────────
	function showUploadToast(message, type) {
		// type: 'loading' | 'success' | 'error'
		var $toast = $("#uploadToast");
		var $spinner = $("#uploadSpinner");
		var $success = $("#uploadSuccess");
		var $error = $("#uploadError");
		var $msg = $("#uploadToastMsg");

		$spinner.hide();
		$success.hide();
		$error.hide();
		$msg.text(message);

		if (type === "loading") {
			$spinner.show();
			$toast.removeClass("toast-success toast-error").addClass("toast-loading");
		} else if (type === "success") {
			$success.show();
			$toast.removeClass("toast-loading toast-error").addClass("toast-success");
		} else {
			$error.show();
			$toast.removeClass("toast-loading toast-success").addClass("toast-error");
		}

		$toast.fadeIn(200);

		// Auto-hide success/error after 4 seconds
		if (type !== "loading") {
			setTimeout(function () {
				$toast.fadeOut(300);
			}, 4000);
		}
	}

	function hideUploadToast() {
		$("#uploadToast").fadeOut(200);
	}

	// ── PDF Upload ──────────────────────────────────────────────
	$("#uploadBtn").on("click", function () {
		$("#pdfUpload").click();
	});

	$("#pdfUpload").on("change", function () {
		var file = this.files[0];
		if (!file) return;

		// Reset input so re-uploading the same file works
		var $input = $(this);

		if (!file.name.toLowerCase().endsWith(".pdf")) {
			showUploadToast("Only PDF files are allowed.", "error");
			$input.val("");
			return;
		}

		// 20 MB check (client-side guard)
		if (file.size > 20 * 1024 * 1024) {
			showUploadToast("File too large. Maximum size is 20 MB.", "error");
			$input.val("");
			return;
		}

		showUploadToast('Uploading "' + file.name + '"...', "loading");

		var formData = new FormData();
		formData.append("pdf", file);

		fetch("/upload_pdf", {
			method: "POST",
			body: formData,
		})
			.then(function (res) {
				return res.json().then(function (data) {
					return { ok: res.ok, data: data };
				});
			})
			.then(function (result) {
				if (result.ok && result.data.success) {
					showUploadToast(result.data.message, "success");
				} else {
					showUploadToast(
						result.data.error || "Upload failed.",
						"error"
					);
				}
			})
			.catch(function () {
				showUploadToast(
					"Network error. Could not upload the PDF.",
					"error"
				);
			})
			.finally(function () {
				$input.val("");
			});
	});

	// ── Chat (SSE streaming) ────────────────────────────────────
	$("#messageArea").on("submit", function (event) {
		event.preventDefault();

		var rawText = $("#text").val().trim();
		if (!rawText) return;

		var time = getTimeString();

		// ─ User bubble
		var userMsgEl = $('<div class="msg_cotainer_send">').text(rawText);
		userMsgEl.append($('<span class="msg_time_send">').text(time));
		var userRow = $('<div class="d-flex justify-content-end mb-4">')
			.append(userMsgEl)
			.append(
				'<div class="img_cont_msg"><img src="https://i.ibb.co/d5b84Xw/Untitled-design.png" class="rounded-circle user_img_msg"></div>'
			);
		$("#messageFormeight").append(userRow);
		$("#text").val("");
		scrollToBottom();

		// ─ Loading indicator
		var $loading = $(
			'<div class="d-flex justify-content-start mb-4" id="loading">'
		)
			.append(
				'<div class="img_cont_msg"><img src="https://cdn-icons-png.flaticon.com/512/387/387569.png" class="rounded-circle user_img_msg"></div>'
			)
			.append(
				$('<div class="msg_cotainer">')
					.html('<i class="fas fa-circle-notch fa-spin"></i> Thinking...')
					.append($('<span class="msg_time">').text(time))
			);
		$("#messageFormeight").append($loading);
		scrollToBottom();
		$("#send").prop("disabled", true);

		// ─ SSE via fetch (POST isn't supported by EventSource, so we read the
		//   stream manually with the fetch API ReadableStream reader.)
		var formData = new FormData();
		formData.append("msg", rawText);

		fetch("/get_stream", {
			method: "POST",
			body: formData,
		})
			.then(function (response) {
				if (!response.ok) {
					throw new Error("Server error: " + response.status);
				}

				// Remove loading, create bot bubble
				$("#loading").remove();
				var $bubble = createBotBubble(time);
				var accumulated = "";

				var reader = response.body.getReader();
				var decoder = new TextDecoder();
				var buffer = "";

				function processChunk(result) {
					if (result.done) {
						// Streaming finished — render final markdown
						try {
							$bubble.contents().not(".msg_time").not(".sources-section").remove();
							var htmlContent = marked.parse(accumulated);
							$bubble.prepend(
								$('<div class="bot-markdown">').html(htmlContent)
							);
						} catch (e) {
							// fallback: plain text
						}
						scrollToBottom();
						$("#send").prop("disabled", false);
						return;
					}

					buffer += decoder.decode(result.value, { stream: true });

					// Parse SSE lines from the buffer
					var lines = buffer.split("\n");
					// Keep the last (potentially incomplete) line in the buffer
					buffer = lines.pop();

					var currentEvent = "";
					for (var i = 0; i < lines.length; i++) {
						var line = lines[i];
						if (line.startsWith("event: ")) {
							currentEvent = line.substring(7).trim();
						} else if (line.startsWith("data: ")) {
							var dataStr = line.substring(6);
							try {
								var data = JSON.parse(dataStr);
							} catch (e) {
								continue;
							}

							if (currentEvent === "token" && data.token) {
								accumulated += data.token;
								// Show plain text while streaming
								$bubble
									.contents()
									.not(".msg_time")
									.not(".sources-section")
									.remove();
								$bubble.prepend(
									document.createTextNode(accumulated)
								);
								scrollToBottom();
							} else if (
								currentEvent === "sources" &&
								data.sources &&
								data.sources.length > 0
							) {
								var $sources = $(
									'<div class="sources-section">'
								);
								$sources.append(
									'<div class="sources-label"><i class="fas fa-book-medical"></i> Sources</div>'
								);
								data.sources.forEach(function (src) {
								var $item = $('<div class="source-item">');
								$item.append($("<strong>").text(src.title));
								$item.append("<br>");
								$item.append($("<small>").text(src.snippet));
								$sources.append($item);
							});
								$bubble.append($sources);
							} else if (currentEvent === "error" && data.error) {
								$bubble
									.contents()
									.not(".msg_time")
									.remove();
								$bubble.prepend(
									document.createTextNode(data.error)
								);
								$("#send").prop("disabled", false);
							}
							// Reset event after processing data
							currentEvent = "";
						}
					}

					return reader.read().then(processChunk);
				}

				return reader.read().then(processChunk);
			})
			.catch(function (err) {
				console.error("Stream error:", err);
				$("#loading").remove();
				var $errBubble = createBotBubble(time);
				$errBubble.prepend(
					document.createTextNode(
						"Sorry, I encountered an error. Please try again."
					)
				);
				$("#send").prop("disabled", false);
			});
	});
});
