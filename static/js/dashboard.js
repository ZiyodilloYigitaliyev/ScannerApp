document.getElementById('getDataBtn').addEventListener('click', function() {
    // API endpoint
    const apiUrl = 'https://scan-app-a3872b370d3e.herokuapp.com/download-zip/'; // O'zingizning haqiqiy API URL manzilingizni yozing

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('API so\'rovi bajarilmadi');
            }
            return response.blob();  // Binary ma'lumotni olish
        })
        .then(blob => {
            // Faylni yuklab olish
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'file.zip';  // Yuklanadigan fayl nomi
            link.click();  // Faylni yuklashni boshlash
        })
        .catch(error => {
            // Xatolikni ko'rsatish
            document.getElementById('dataOutput').textContent = `Xatolik: ${error.message}`;
        });
});

document.addEventListener('DOMContentLoaded', function() {
    const fileForm = document.getElementById("fileForm");
    const fileFieldsContainer = document.getElementById("fileFieldsContainer");
    const addFileBtn = document.getElementById("addFileBtn");
    const submitBtn = document.getElementById("submitBtn");

    let fileCount = 0; // Fayl soni

    // Fayl qo'shish funksiyasi
    function addFileField() {
        if (fileCount >= 5) {
            alert("Fayllarni maksimal 5 ta yuborishingiz mumkin.");
            return;
        }

        fileCount++;

        const fileFieldHTML = `
            <div class="file-fields" id="fileField${fileCount}">
                <label for="fileInput${fileCount}">Fayl ${fileCount}:</label>
                <input type="file" id="fileInput${fileCount}" name="files" accept=".zip" required>
                
                <label for="categorySelect${fileCount}">Kategoriya:</label>
                <select id="categorySelect${fileCount}" name="category" required>
                    <option value="">Kategoriya tanlang</option>
                    <option value="Majburiy_fan_1">Majburiy_fan_1</option>
                    <option value="Majburiy_fan_2">Majburiy_fan_2</option>
                    <option value="Majburiy_fan_3">Majburiy_fan_3</option>
                    <option value="Fan_1">Fan_1</option>
                    <option value="Fan_2">Fan_2</option>
                </select>

                <label for="subjectSelect${fileCount}">Mavzu:</label>
                <select id="subjectSelect${fileCount}" name="subject" required>
                    <option value="">Mavzu tanlang</option>
                    <option value="Algebra">Algebra</option>
                    <option value="Geometriya">Geometriya</option>
                    <option value="Kimyo">Kimyo</option>
                    <option value="Fizika">Fizika</option>
                    <option value="Ona tili">Ona tili</option> 
                </select>
                
                <!-- Remove button -->
                <button type="button" class="remove-file-btn" data-file="${fileCount}">-</button>
            </div>
        `;

        fileFieldsContainer.insertAdjacentHTML("beforeend", fileFieldHTML);

        // Har bir yangi fayl uchun "remove" tugmasining event listenerini qo'shish
        const removeBtn = document.querySelector(`#fileField${fileCount} .remove-file-btn`);
        removeBtn.addEventListener("click", function() {
            removeFileField(fileCount);
        });
    }

    // Fayl qo'shish tugmasi
    addFileBtn.addEventListener("click", addFileField);

    // Faylni olib tashlash funksiyasi
    window.removeFileField = function(fileNumber) {
        const fileField = document.getElementById(`fileField${fileNumber}`);
        fileFieldsContainer.removeChild(fileField);
        fileCount--;
    }
    function clearForm() {
        fileFieldsContainer.innerHTML = "";
        fileForm.reset();
        fileCount = 0;
    }

    function handleTokenExpiration(response) {
        if (response.status === 401) {
            alert("Token vaqti tugagan. Login sahifasiga yo'naltirilasiz.");
            window.location.href = "/login"; // Login sahifasiga yo'naltirish
            throw new Error("Token vaqti tugagan.");
        }
        return response;
    }
    // Formani yuborish
    fileForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const formData = new FormData(fileForm);
        const token = localStorage.getItem("jwt_token");

        if (!token) {
            alert("JWT token topilmadi!");
            return;
        }

        try {
            // Fayllarni yuklash
            await fetch("https://create-test-app-100ceac94608.herokuapp.com/upload/", {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                },
                body: formData,
            });

            const additional_value = prompt("Nechta savol kerakligini kiriting:");
            if (!additional_value) {
                alert("Savollar soni kiritilmagan.");
                return;
            }

            const response = await fetch("https://create-test-app-100ceac94608.herokuapp.com/questions/");
            if (!response.ok) throw new Error("Savollarni olishda xatolik yuz berdi.");
            const data = await response.json();

            const requestData = [
                {
                    num: { additional_value: parseInt(additional_value) },
                    ...data
                },
            ];
            const postResponse = await fetch("https://scan-app-a3872b370d3e.herokuapp.com/api/questions/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestData),

            });

            if (!postResponse.ok) throw new Error("Savollarni yuborishda xatolik yuz berdi.");

            alert("Savollar muvaffaqiyatli yuborildi!");

            await fetch("https://create-test-app-100ceac94608.herokuapp.com/delete-all-questions/", { method: "DELETE" });
            fileForm.reset();
        } catch (error) {
            console.error(error.message);
            alert("Xatolik yuz berdi: " + error.message);
        }
    });
});