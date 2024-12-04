//** @odoo-module */

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class DiscussCustomSidebar extends Component {
  constructor() {
    super(...arguments);

    this.state = useState({
      selectedUserName: "",
      selectedUserId: null,
      users: [],
      channels: [],
      directMessages: [],
      selectedChannel: null,
      messages: [],
      isShowMemberList: false,
      members: [],
      searchResults: [],
    });
  }

  setup() {
    super.setup();
    this.state = useState({
      selectedUserName: "",
      selectedUserId: null,
      users: [],
      channels: [],
      directMessages: [],
      selectedChannel: null,
      messages: [], attachments: [],
      searchResults: [],
    });
    this.onSearchInput = this.onSearchInput.bind(this);
    this.searchInputRef = useRef("searchInput");
    this.rpc = useService("rpc");
    this.prevMessage = null;
    this.currentDate = null;
    onWillStart(async () => {
      const permissions = await this.checkUserPermissions();
      this.state.isAdmin = permissions.isAdmin;
      
    });
  }

  
  async selectSearchedUser(user) {
    this.state.selectedUserName = user.name;
    this.state.selectedUserId = user.id;
    this.state.searchResults = [];
    
    if (this.searchInputRef && this.searchInputRef.el) {
      this.searchInputRef.el.value = user.name;
    } else {
      console.warn("Search input reference is not available");
    }
    
    console.log("ID người dùng:", user.id);
    await this.fetchChannels(user.id);
  }
// Thêm các phương thức mới
onSearchInput(event) {
  
  const searchTerm = event.target.value.trim();
  if (searchTerm.length > 0) {
    this.searchUsers(searchTerm);
  } else {
    this.clearSearch();
  }
}
async searchUsers(searchTerm) {
  try {
    const response = await this.rpc("/search_users", {
      search_term: searchTerm,
    });
    if (response && response.users) {
      this.state.searchResults = response.users;
    } else {
      console.error("Error searching users:", response.error || "Unknown error");
      this.state.searchResults = [];
    }
  } catch (error) {
    console.error("Error in searchUsers:", error);
    this.state.searchResults = [];
  }
}

clearSearch() {
  if (this.searchInputRef.el) {
    this.searchInputRef.el.value = "";
  }
  this.state.searchResults = [];
  this.state.selectedUserName = "";
  this.state.selectedUserId = null;
  // Xóa thông tin channel
  this.state.channels = [];
  this.state.directMessages = [];
  this.state.selectedChannel = null;
  this.state.messages = [];
  this.state.members = [];
  this.state.isShowMemberList = false;
}

  async fetchChannels(userId) {
    try {

      if (!this.state.isAdmin && !this.state.isUser) {
        console.error("User does not have permission to fetch channels");
        return;
      }

      const response = await this.rpc(`/get_mail_channels_tien/${userId}`, {
        method: "POST",
      });
      if (!response.error) {
        console.log(
          "Đã tải channel: ",
          JSON.stringify(response.channels, null, 2)
        );
        this.state.channels = response.channels;
        this.state.channels = response.channels.filter(
          (ch) => ch.channel_type === "channel"
        );
        this.state.directMessages = response.channels.filter(
          (ch) => ch.channel_type === "chat"
        );
      } else {
        console.log("Lỗi tải dữ liệu channel");
      }
    } catch (error) {
      console.error("Error in fetching channels:", error);
      this.state.channels = [];
      this.state.directMessages = [];
    }
  }

  // Cập nhật state khi một kênh hoặc tin nhắn trực tiếp được chọn
  handleChannel(channel) {
    console.log("Thông tin channel:", channel);
    if (channel && channel.id) {
      this.loadChannelData(channel);
    } else {
      console.error("Invalid channel object:", channel);
    }
  }

  async loadChannelData(channel) {
    try {

      if (!this.state.isAdmin && !this.state.isUser) {
        console.error("User does not have permission to load channel data");
        return;
      }
      
      this.state.selectedChannel = { ...channel };
      this.state.messages = [];

      const channelInfo = await this.rpc("/get_mail_channel_info", {
        channel_id: channel.id,
      });
      
      if (channelInfo.error) {
        console.error("lỗi khi xử lý channel:", channelInfo.error);
        return;
      }

      this.state.selectedChannel = {
        ...this.state.selectedChannel,
        name: channelInfo.name,
        description: channelInfo.description,
      };

      const messageHistory = await this.rpc(`/tien/chat_full_history`, {
        channel_id: channel.id,
      });

      if (!messageHistory.error) {
        this.state.messages = messageHistory.messages.map(message => ({
            ...message,
            formattedBody: this.checkFormatMessageBody(message.body, message.author_id[1]),
            replyTo: message.reply_to ? {
                ...message.reply_to,
                formattedBody: this.checkFormatMessageBody(message.reply_to.body, message.reply_to.author_name)
            } : null
        }));
        console.log("Dữ liệu tin nhắn:", this.state.messages);
    } else {
        console.error("Lỗi khi tải tin nhắn:", messageHistory.error);
    }

      this.render();
    } catch (error) {
      console.error("Lỗi khi tải channel:", error);
      this.state.selectedChannel = null;
      this.state.messages = [];
    }
  }

  formatDate(dateString) {
    const options = { year: "numeric", month: "long", day: "numeric" };
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", options);
  }

  calculateDaysAgo(dateString) {
    const createdDate = new Date(dateString); // Ngày tạo
    const currentDate = new Date(); // Ngày hiện tại

    // Tính chênh lệch thời gian giữa hai ngày (mili giây)
    const timeDifference = currentDate - createdDate;

    // Chuyển đổi mili giây thành số ngày
    const daysDifference = Math.floor(timeDifference / (1000 * 60 * 60 * 24));

    // Trả về kết quả với định dạng "X days ago"
    return daysDifference > 0 ? `${daysDifference} days ago` : "Today";
  }
  async checkUserPermissions() {
    try {
      const response = await this.rpc("/check_discuss_custom_permissions", {});
      return response.permissions;
    } catch (error) {
      console.error("Error checking user permissions:", error);
      return {
        isAdmin: false,
       
      };
    }
  }
  checkFormatMessageBody(messageBody, authorName) {
    // Kiểm tra dạng 3: Nội dung chứa thẻ div với class "o_mail_notification"
    if (messageBody.trim().startsWith('<div class="o_mail_notification">')) {
      return {
        type: 'notification',
        content: this.formatNotification(messageBody, authorName)
      };
    }

    // Kiểm tra dạng 1: Nội dung chứa đoạn <p>
    if (messageBody.trim().startsWith('<p>')) {
      return {
        type: 'regular',
        content: this.formatHTMLToText(messageBody)
      };
    }

    // Kiểm tra dạng 2: Nội dung là khoảng trắng (file đính kèm)
    if (!messageBody.trim()) {
      return {
        type: 'attachment',
        content: ""
      };
    }

    return {
      type: 'unknown',
      content: "Unknown format"
    };
  }

  // Hàm chuyển đổi HTML thành văn bản
  formatHTMLToText(htmlString) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, "text/html");

    const textNodes = doc.body.querySelectorAll("*");

    let formattedText = "";

    textNodes.forEach((node) => {
      if (node.textContent.trim()) {
        formattedText += node.textContent.trim() + "\n";
      }
    });

    return formattedText.trim();
  }

  formatNotification(htmlString, authorName) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, "text/html");

    // Tìm nội dung của thông báo
    const notificationContent = doc.querySelector(".o_mail_notification");

    // Nếu không có nội dung phù hợp, trả về chuỗi ban đầu
    if (!notificationContent) {
      return htmlString;
    }

    // Tìm tên channel
    const channelLink = notificationContent.querySelector(".o_channel_redirect");
    const channelName = channelLink ? channelLink.textContent : "unknown channel";

    // Tạo cấu trúc mới cho thông báo
    const formattedNotification = `${authorName} ${notificationContent.textContent.replace(channelName, `${channelName}`)}`;

    return formattedNotification.trim();
  }

  // Hàm gọi API để lấy danh sách thành viên của kênh chat
  async loadMemberList(channelId) {
    try {
      const response = await this.rpc("/get_chat_group_members", {
        channel_id: channelId,
      });
      if (response.error) {
        console.error("Lỗi khi lấy danh sách thành viên:", response.error);
      } else {
        this.state.members = response.members; // Lưu danh sách thành viên vào state
      }
    } catch (error) {
      console.error("Lỗi khi gọi API loadMemberList:", error);
    }
  }
  shouldDisplayHeader(message) {
    const messageDate = this.formatDate(message.date);
    if (messageDate !== this.currentDate) {
      this.currentDate = messageDate;
      return true;
    }
    return false;
  }

  // Thêm phương thức mới để kiểm tra tránh hiển thị avatar bị trùng
  shouldDisplayAvatar(message) {
    // Nếu là thông báo hệ thống, không hiển thị avatar
    if (this.isNotification(message)) {
      this.prevMessage = null;
      return false;
    }
   return this.shouldDisplayAvatarForRegularMessage(message);
   
  }

  shouldDisplayAvatarForRegularMessage(message) {
    if (!this.prevMessage) {
      return true;
    }
    const sameAuthor = this.prevMessage.author_id[0] === message.author_id[0];
    const sameDate = this.formatDate(this.prevMessage.date) === this.formatDate(message.date);
    return !(sameAuthor && sameDate);
  }

  updatePrevMessage(message) {
    // Chỉ cập nhật prevMessage nếu tin nhắn không phải là thông báo
    if (!this.isNotification(message)) {
        this.prevMessage = message;
    }
  }


  // Hàm xử lý khi người dùng nhấn nút hiển thị danh sách thành viên
  async onClickShowMemberList() {
    if (!this.state.selectedUserId) {
      // Nếu chưa chọn người dùng
      this.showNotification("Vui lòng chọn người dùng trước khi xem danh sách thành viên.");
      return;
    }

    if (!this.state.selectedChannel) {
      // Nếu đã chọn người dùng nhưng chưa chọn channel
      this.showNotification("Vui lòng chọn một kênh trước khi xem danh sách thành viên.");
      return;
    }

    await this.loadMemberList(this.state.selectedChannel.id);
    this.state.isShowMemberList = true;
  }

   showNotification(message) {
    // Sử dụng service notification của Odoo nếu có
    const notificationService = this.env.services.notification;
    if (notificationService) {
      notificationService.add(message, {
        type: 'warning',
        sticky: false,
        className: 'o_discuss_custom_notification',
      });
    } else {
      
      alert(message);
    }
  }

  // Hàm xử lý khi người dùng nhấn nút ẩn danh sách thành viên
  onClickHideMemberList() {
    this.state.isShowMemberList = false; // Ẩn danh sách
  }
  getFileExtension(filename) {
    return filename.split('.').pop().toUpperCase();
  }
 
 // Add this new method to fetch attachments
 async fetchAttachments() {
  try {
    const response = await this.rpc("/attachments", {});
    if (response.attachments) {
      this.state.attachments = response.attachments;
      console.log("Fetched attachments:", this.state.attachments);
    } else {
      console.error("Error fetching attachments:", response.error);
    }
  } catch (error) {
    console.error("Error in fetchAttachments:", error);
  }
}

  formatHTMLToText(html) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    return tempDiv.textContent || tempDiv.innerText || '';
  }
  isNotification(message) {
    return message.body.trim().startsWith('<div class="o_mail_notification">');
  }

 
}

DiscussCustomSidebar.template = "discuss_custom.DiscussCustomSidebar";
DiscussCustomSidebar.components = {};

export const discussCustomSidebarComponent = DiscussCustomSidebar;

// Đăng ký component cho settings
const settingsRegistry = registry.category("view_widgets");
settingsRegistry.add("discuss_custom_sidebar", DiscussCustomSidebar);